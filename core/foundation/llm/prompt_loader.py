"""【重点3】提示词加载器 —— 每个 LLM 环节的 system / user 提示词均可被用户修改.

优先级 (从高到低):
  1. config.yaml 的 llm.prompts.{stage}.system / user (非空时覆盖)
  2. prompts/{stage}.system.md / prompts/{stage}.user.md 文件
  3. 代码内置兜底 (传入的 default_system / default_user)

user 模板用 `{{占位符}}` 注入运行时变量 (双花括号, 避免与 JSON 示例里的单花括号冲突).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


class PromptLoader:
    def __init__(self, prompts_dir: str | Path, config_prompts: Optional[dict[str, Any]] = None) -> None:
        self.dir = Path(prompts_dir)
        self.cfg = config_prompts or {}

    # ---------- system ----------
    def _find_prompt_file(self, stage: str, kind: str) -> Path | None:
        """支持 prompts/ 根目录与 planning/locating/reliability/assertion 子目录."""
        name = f"{stage}.{kind}.md"
        direct = self.dir / name
        if direct.is_file():
            return direct
        subdirs = ("planning", "locating", "reliability", "assertion")
        stage_map = {
            "action_plan": "planning",
            "precondition": "planning",
            "case_sort": "planning",
            "element_decide": "locating",
            "readiness": "reliability",
            "readiness_gate": "reliability",
            "post_check": "reliability",
            "retry_plan": "reliability",
            "semantic_assert": "assertion",
        }
        sub = stage_map.get(stage)
        if sub:
            cand = self.dir / sub / name
            if cand.is_file():
                return cand
        for sub in subdirs:
            cand = self.dir / sub / name
            if cand.is_file():
                return cand
        return None

    def system(self, stage: str, default: str = "") -> str:
        override = self._cfg_value(stage, "system")
        if override:
            return override
        f = self._find_prompt_file(stage, "system")
        if f and f.exists():
            return f.read_text(encoding="utf-8")
        return default

    def user(self, stage: str, default: str = "", **kwargs: Any) -> str:
        override = self._cfg_value(stage, "user")
        if override:
            template = override
        else:
            f = self._find_prompt_file(stage, "user")
            template = f.read_text(encoding="utf-8") if f and f.exists() else default
        return _render(template, kwargs)

    def load(self, stage: str, default_system: str = "", default_user: str = "", **kwargs: Any) -> tuple[str, str]:
        return self.system(stage, default_system), self.user(stage, default_user, **kwargs)

    def _cfg_value(self, stage: str, key: str) -> str:
        node = self.cfg.get(stage) or {}
        if isinstance(node, dict):
            v = node.get(key)
            if isinstance(v, str) and v.strip():
                return v
        return ""


def _render(template: str, kwargs: dict[str, Any]) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", "" if v is None else str(v))
    return out
