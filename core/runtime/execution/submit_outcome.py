"""提交结果通用模型 —— 自动识别上下文, 按信号判定是否推进.

三阶段:
1. classify_submit_context(url, dom) → DETAIL_URL | LIST_EMBED | UNKNOWN
2. capture_submit_snapshot / poll → navigation_outcome + entity before/after
3. evaluate_submit_outcome → 本地 step_ok 短路 (LIST_EMBED/DETAIL 成功信号)

不绑定业务 URL 字面量; 实体 ID 来自 entity_discover.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .entity_discover import discover_dom_entity_ids, discover_page_entity
from .script_helpers import (
    _body_has_submit_error,
    _read_body_safe,
    is_detail_submission_url,
)

# 与 tab_follow / nav_progress / submit_post_verify 对齐
SUCCESS_OUTCOMES = frozenset({
    "resource_id_changed",
    "returned_to_list",
    "route_changed",
    "list_empty",
})

AMBIGUOUS_OUTCOMES = frozenset({"timeout", "settled"})

_LIST_EMPTY_MARKERS = ("暂无题目", "请去任务中心领题")


class SubmitContextKind(str, Enum):
    """提交发生时页面上下文 (运行时推断, 零业务配置)."""

    DETAIL_URL = "detail_url"   # URL 携带实体 ID (/detail?uniqId=...)
    LIST_EMBED = "list_embed"   # 同路由内嵌详情, 实体在 DOM
    UNKNOWN = "unknown"


@dataclass
class SubmitSnapshot:
    """点击提交前的基线."""

    url: str = ""
    entity_id: str = ""
    entity_field: str = ""
    context: SubmitContextKind = SubmitContextKind.UNKNOWN
    body_excerpt: str = ""


@dataclass
class SubmitOutcomeFacts:
    """提交等待/后校验时刻的结构化事实."""

    context: SubmitContextKind = SubmitContextKind.UNKNOWN
    navigation_outcome: str = ""
    url_before: str = ""
    url_after: str = ""
    entity_id_before: str = ""
    entity_id_after: str = ""
    entity_field: str = ""

    @property
    def entity_changed(self) -> bool:
        return bool(
            self.entity_id_before
            and self.entity_id_after
            and self.entity_id_before != self.entity_id_after,
        )

    @property
    def url_changed(self) -> bool:
        return bool(
            self.url_before
            and self.url_after
            and self.url_before.strip() != self.url_after.strip(),
        )

    def format_for_prompt(self) -> str:
        ctx = self.context.value
        lines = [
            "【提交后结构化事实】(优先据此判断, 勿仅凭 URL 是否变化)",
            f"- submit_context: {ctx}",
            f"- 提交前实体({self.entity_field or 'entity'}): {self.entity_id_before or '(未记录)'}",
            f"- 提交后实体: {self.entity_id_after or '(未解析)'}",
            f"- 实体是否切换: {'是' if self.entity_changed else '否'}",
            f"- navigation_outcome: {self.navigation_outcome or '(无)'}",
            f"- url_before: {(self.url_before or '')[:120]}",
            f"- url_after: {(self.url_after or '')[:120]}",
        ]
        if self.context == SubmitContextKind.LIST_EMBED:
            lines.append(
                "- 说明: LIST_EMBED 上下文提交后 URL 通常不变; "
                "成功=空态文案或 DOM 实体切换, 失败=同实体且无推进信号"
            )
        return "\n".join(lines)


def body_has_list_empty_state(body: str) -> bool:
    text = body or ""
    return any(m in text for m in _LIST_EMPTY_MARKERS)


def classify_submit_context(
    url: str,
    *,
    flat_text: str = "",
) -> SubmitContextKind:
    """推断提交上下文."""
    if is_detail_submission_url(url):
        return SubmitContextKind.DETAIL_URL
    if discover_dom_entity_ids(flat_text):
        return SubmitContextKind.LIST_EMBED
    return SubmitContextKind.UNKNOWN


def capture_submit_snapshot(
    *,
    url: str,
    flat_text: str = "",
    api_context: Optional[dict[str, Any]] = None,
) -> SubmitSnapshot:
    """提交 click 前采集基线."""
    ctx = api_context or {}
    context = classify_submit_context(url, flat_text=flat_text)
    eid, field = discover_page_entity(ctx, url=url, flat_text=flat_text)
    return SubmitSnapshot(
        url=url or "",
        entity_id=eid,
        entity_field=field,
        context=context,
        body_excerpt=(flat_text or "")[:6000],
    )


def detect_list_embed_progress(
    body: str,
    *,
    entity_before: str = "",
) -> Optional[str]:
    """LIST_EMBED 同 URL 下的 DOM 推进信号 → navigation_outcome."""
    if body_has_list_empty_state(body):
        return "list_empty"
    if entity_before:
        dom_ids = discover_dom_entity_ids(body)
        if dom_ids and dom_ids[0][1] != entity_before:
            return "resource_id_changed"
    return None


def build_outcome_facts(
    meta: dict[str, Any],
    *,
    dom_summary: Optional[str] = None,
    api_context: Optional[dict[str, Any]] = None,
) -> SubmitOutcomeFacts:
    """从 dispatch meta + DOM 构造提交事实."""
    ctx = api_context or {}
    url_before = str(meta.get("url_before") or "")
    url_after = str(meta.get("url_after") or url_before)
    text = (dom_summary or "").strip()
    id_before = str(meta.get("entity_id_before") or "")
    id_after = str(meta.get("entity_id_after") or "")
    field = str(meta.get("entity_field") or "")
    if not id_after and text:
        id_after, field_dom = discover_page_entity(ctx, url=url_after, flat_text=text)
        field = field or field_dom
    context = classify_submit_context(url_before, flat_text=text)
    if context == SubmitContextKind.UNKNOWN and id_before and not is_detail_submission_url(url_before):
        context = SubmitContextKind.LIST_EMBED
    outcome = str(meta.get("navigation_outcome") or "")
    if not outcome and text:
        embed = detect_list_embed_progress(text, entity_before=id_before)
        if embed:
            outcome = embed
    if id_before and id_after and id_before != id_after and not outcome:
        outcome = "resource_id_changed"
    return SubmitOutcomeFacts(
        context=context,
        navigation_outcome=outcome,
        url_before=url_before,
        url_after=url_after,
        entity_id_before=id_before,
        entity_id_after=id_after,
        entity_field=field,
    )


def evaluate_submit_outcome(
    facts: SubmitOutcomeFacts,
    *,
    dom_summary: Optional[str] = None,
    dispatch_ok: bool = True,
) -> Optional[tuple[bool, str]]:
    """本地判定提交是否推进. 返回 None 表示交 LLM.

    Returns:
        (step_ok, reason) or None
    """
    if not dispatch_ok:
        return False, "提交按钮未成功点击, 无法判断提交结果"

    text = (dom_summary or "").strip()
    if text and _body_has_submit_error(text):
        return False, "提交后页面提示提交失败或未生效"

    outcome = facts.navigation_outcome

    if outcome == "submit_error":
        return False, "提交后页面提示错误"

    if outcome in SUCCESS_OUTCOMES:
        return _success_reason(facts, outcome)

    # LIST_EMBED: DOM 空态 / 实体切换 (outcome 可能仍为 settled)
    if facts.context == SubmitContextKind.LIST_EMBED:
        if text and body_has_list_empty_state(text):
            return True, "提交后进入空态(暂无题目/请去任务中心领题), 同路由 URL 不变属正常"
        if facts.entity_changed:
            return (
                True,
                f"提交后 DOM 实体已切换 "
                f"({facts.entity_id_before} → {facts.entity_id_after})",
            )
        embed = detect_list_embed_progress(text, entity_before=facts.entity_id_before)
        if embed == "list_empty":
            return True, "提交后进入空态, URL 可不变"
        if embed == "resource_id_changed":
            return True, "提交后同页切换下一条任务"

    # DETAIL_URL: 实体/导航 outcome 已在 SUCCESS 分支; settled 且同实体 → 模糊
    if facts.context == SubmitContextKind.DETAIL_URL:
        if facts.entity_changed:
            return (
                True,
                f"提交后实体已切换 "
                f"({facts.entity_id_before} → {facts.entity_id_after})",
            )
        if outcome == "returned_to_list" or facts.url_changed:
            return True, "提交后已离开详情上下文"

    return None


def _success_reason(facts: SubmitOutcomeFacts, outcome: str) -> tuple[bool, str]:
    if outcome == "list_empty":
        return True, "提交后进入空态(无剩余待办)"
    if outcome == "returned_to_list":
        return True, "提交后已回到列表页"
    if outcome in ("resource_id_changed", "route_changed"):
        detail = ""
        if facts.entity_changed:
            detail = f" ({facts.entity_id_before} → {facts.entity_id_after})"
        return True, f"提交后页面已推进 ({outcome}){detail}"
    return True, f"提交后 navigation_outcome={outcome}"


def read_page_body(page: Any, dom_summary: Optional[str] = None) -> str:
    if (dom_summary or "").strip():
        return dom_summary.strip()
    return _read_body_safe(page)
