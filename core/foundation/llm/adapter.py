"""步骤⑱ 大模型适配器 —— 所有 AI 能力的底层驱动.

封装 OpenAI 兼容接口, 提供:
  - complete_json(): 返回 LLMResult(含解析后的 dict + 原始文本 + 完整提示词)
  - complete_text(): 返回纯文本
  - 失败重试 + JSON 提取 (复用 core.llm_client._extract_json)
  - 观测回调 (on_call): 把完整提示词和原始返回交给可观测性收集器

配置 (config.yaml → llm):
  - provider: 默认供应商名 (未在 stages 中指定的环节使用)
  - <provider_name>: 各供应商的 base_url / api_key / model
  - stages: 可选, 按环节覆盖供应商, 如 action_plan: opus
  - prompts.<stage>.provider: 可选, 与 stages 等价 (stages 优先)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

# 复用旧实现的 JSON 提取 (字符串感知括号计数法)
from ...foundation.llm_client import _extract_json

_LLM_META_KEYS = frozenset({
    "provider", "max_tokens", "temperature", "prompts", "stages",
})


@dataclass(frozen=True)
class _ProviderRuntime:
    provider: str
    model: str
    client: Any
    use_response_format: bool


@dataclass
class LLMResult:
    """一次 LLM 调用的结构化结果, 同时保留原始文本便于排查."""

    data: dict[str, Any]
    raw: str
    system: str
    user: str


# 观测回调签名: (stage, system, user, raw) -> None
ObserveFn = Callable[[str, str, str, str], None]


def resolve_stage_provider(llm_cfg: dict[str, Any], stage: str) -> str:
    """解析环节使用的 provider 名: stages > prompts.<stage>.provider > llm.provider."""
    stage = (stage or "").strip()
    stages = llm_cfg.get("stages") or {}
    if stage and isinstance(stages, dict):
        mapped = stages.get(stage)
        if isinstance(mapped, str) and mapped.strip():
            return mapped.strip()
    prompts = llm_cfg.get("prompts") or {}
    if stage and isinstance(prompts, dict):
        node = prompts.get(stage) or {}
        if isinstance(node, dict):
            mapped = node.get("provider")
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()
    return (llm_cfg.get("provider") or "ollama").strip()


def _provider_subcfg(llm_cfg: dict[str, Any], provider: str) -> dict[str, Any]:
    sub = llm_cfg.get(provider)
    if not isinstance(sub, dict) or not sub:
        known = [
            k for k, v in llm_cfg.items()
            if k not in _LLM_META_KEYS and isinstance(v, dict) and v.get("base_url")
        ]
        hint = f"可选: {', '.join(sorted(known))}" if known else "请在 llm 下配置对应供应商块"
        raise ValueError(f"未知或未配置的 LLM provider: {provider!r} ({hint})")
    return sub


class LLMAdapter:
    """统一封装不同 OpenAI 兼容模型供应商的调用细节."""

    def __init__(
        self,
        llm_cfg: dict[str, Any],
        max_retries: int = 2,
        retry_delay_s: float = 1.0,
        observe: Optional[ObserveFn] = None,
    ) -> None:
        self._cfg = llm_cfg
        self._max_retries = max_retries
        self._retry_delay = retry_delay_s
        self._observe = observe
        self._max_tokens = int(llm_cfg.get("max_tokens", 2048))
        self._temperature = float(llm_cfg.get("temperature", 0.0))
        self._runtimes: dict[str, _ProviderRuntime] = {}
        default_provider = resolve_stage_provider(llm_cfg, "")
        self.provider = default_provider
        self.model = _provider_subcfg(llm_cfg, default_provider).get("model", "")

    def provider_for_stage(self, stage: str) -> str:
        return resolve_stage_provider(self._cfg, stage)

    def model_for_stage(self, stage: str) -> str:
        return _provider_subcfg(self._cfg, self.provider_for_stage(stage)).get("model", "")

    def _runtime_for_stage(self, stage: str) -> _ProviderRuntime:
        provider = self.provider_for_stage(stage)
        cached = self._runtimes.get(provider)
        if cached is not None:
            return cached
        from openai import OpenAI

        sub = _provider_subcfg(self._cfg, provider)
        base_url = (sub.get("base_url") or "").rstrip("/")
        if base_url and not base_url.endswith("/v1"):
            base_url += "/v1"
        runtime = _ProviderRuntime(
            provider=provider,
            model=str(sub.get("model") or ""),
            client=OpenAI(
                api_key=sub.get("api_key") or "ollama",
                base_url=base_url or "http://localhost:11434/v1",
                timeout=int(sub.get("timeout_seconds", 120)),
            ),
            use_response_format=provider != "ollama",
        )
        self._runtimes[provider] = runtime
        return runtime

    def _chat(
        self,
        stage: str,
        system: str,
        user: str,
        examples: Optional[list[dict]],
        json_mode: bool,
    ) -> str:
        """构造 messages 并调用 chat.completions, 返回模型原始文本."""
        rt = self._runtime_for_stage(stage)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for ex in examples or []:
            messages.append({"role": "user", "content": ex["input"]})
            messages.append({
                "role": "assistant",
                "content": ex["output"] if isinstance(ex["output"], str) else _dumps(ex["output"]),
            })
        messages.append({"role": "user", "content": user})

        kwargs: dict[str, Any] = dict(
            model=rt.model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=messages,
        )
        if json_mode and rt.use_response_format:
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = rt.client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as e:  # noqa: BLE001
                last_err = e
                err = str(e).lower()
                if "response_format" in kwargs and "response_format" in err:
                    kwargs.pop("response_format", None)
                    continue
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay)
                    continue
                raise
        raise last_err  # type: ignore[misc]

    def complete_json(
        self,
        stage: str,
        system: str,
        user: str,
        examples: Optional[list[dict]] = None,
    ) -> LLMResult:
        last_raw = ""
        last_err: Optional[Exception] = None
        for _attempt in range(self._max_retries + 1):
            raw = self._chat(stage, system, user, examples, json_mode=True)
            last_raw = raw
            if self._observe:
                self._observe(stage, system, user, raw)
            try:
                data = _extract_json(raw)
                return LLMResult(data=data, raw=raw, system=system, user=user)
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
        raise ValueError(
            f"{stage} 返回非法JSON, 已重试{self._max_retries}次: {last_err}\n原始: {last_raw[:300]}"
        )

    def complete_text(self, stage: str, system: str, user: str) -> str:
        raw = self._chat(stage, system, user, None, json_mode=False)
        if self._observe:
            self._observe(stage, system, user, raw)
        return raw


def _dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
