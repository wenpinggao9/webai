"""提交类步骤: tab 恢复 + 本地后校验.

- 详情页提交: tab 恢复 + navigation_outcome 推断 (可升级 dispatch_ok).
- 列表内嵌详情: URL 不变, 以 DOM 实体/空态判定 (submit_outcome 模块).
- 本地短路: dispatch 失败 → 不进 LLM 判「页面已满足意图」.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .script_helpers import (
    _body_has_submit_error,
    _page_alive,
    _page_usable,
    _read_body_safe,
    _url_safe,
    find_newest_non_anchor_tab,
    find_usable_context_pages,
    is_detail_submission_url,
    pick_surviving_tab_after_detail_close,
    still_on_same_detail_after_submit,
    submit_left_detail_context,
    _context_from_any,
)
from .submit_outcome import (
    SUCCESS_OUTCOMES,
    AMBIGUOUS_OUTCOMES,
    SubmitContextKind,
    build_outcome_facts,
    evaluate_submit_outcome,
)

_AMBIGUOUS_OUTCOMES = AMBIGUOUS_OUTCOMES
_SUCCESS_OUTCOMES = SUCCESS_OUTCOMES


def is_submit_intent(intent: str) -> bool:
    return "提交" in (intent or "")


def submit_dispatch_should_succeed(meta: dict[str, Any]) -> bool:
    """提交 click 后 dispatch 是否应报成功 (含 tab 关闭但已回列表).

    仅当 meta 含 submit_click_ok 时推断; 否则视为未点到按钮.
    """
    if not meta.get("submit_click_ok"):
        return False
    outcome = str(meta.get("navigation_outcome") or "")
    url_before = str(meta.get("url_before") or "")
    if outcome == "submit_error":
        return False
    if outcome in _SUCCESS_OUTCOMES:
        return True
    if meta.get("left_detail_context") and is_detail_submission_url(url_before):
        return True
    if outcome in _AMBIGUOUS_OUTCOMES:
        if meta.get("left_detail_context"):
            return True
        if meta.get("submit_click_ok") and is_detail_submission_url(url_before):
            if meta.get("recovered") or meta.get("detail_tab_closed"):
                return True
        # LIST_EMBED: entity 已切换也算成功
        id_b = str(meta.get("entity_id_before") or "")
        id_a = str(meta.get("entity_id_after") or "")
        if id_b and id_a and id_b != id_a:
            return True
        ctx = str(meta.get("submit_context") or "")
        if ctx == SubmitContextKind.LIST_EMBED.value and outcome == "settled":
            return False
    return True


@dataclass
class SubmitFinalizeResult:
    page: Any
    meta: dict[str, Any]
    dispatch_ok: bool
    message: Optional[str] = None


def finalize_submit_after_dispatch(
    page: Any,
    meta: Optional[dict[str, Any]],
    *,
    list_anchor: Any = None,
    dispatch_ok: bool = False,
) -> SubmitFinalizeResult:
    """提交 dispatch 后: 切存活 tab, 升级 meta, 决定 dispatch 是否应成功."""
    meta = dict(meta or {})
    url_before = str(meta.get("url_before") or "")
    if not is_detail_submission_url(url_before):
        return SubmitFinalizeResult(page, meta, dispatch_ok)

    outcome = str(meta.get("navigation_outcome") or "")
    url_before = str(meta.get("url_before") or "")

    # 同 tab 切下一任务: 保持 active, 勿 pick_surviving 误切 anchor
    if outcome in ("resource_id_changed", "route_changed") and is_detail_submission_url(url_before):
        target = page if _page_alive(page) else find_newest_non_anchor_tab(
            _context_from_any(page, list_anchor), list_anchor, page,
        )
        if target is not None and _page_alive(target):
            url_now = _url_safe(target)
            meta["url_after"] = url_now or str(meta.get("url_after") or "")
            meta["left_detail_context"] = False
            try:
                target.bring_to_front()
            except Exception:
                pass
            if meta.get("submit_click_ok"):
                dispatch_ok = submit_dispatch_should_succeed(meta)
            return SubmitFinalizeResult(target, meta, dispatch_ok)

    page, rec, url_now, left = pick_surviving_tab_after_detail_close(
        page, url_before=url_before, list_anchor=list_anchor,
    )
    if not _page_alive(page) and is_detail_submission_url(url_before):
        meta["detail_tab_closed"] = True
    if url_now or rec or left:
        meta["url_after"] = url_now or str(meta.get("url_after") or "")
        meta["recovered"] = bool(meta.get("recovered")) or rec or left

    if left:
        meta["left_detail_context"] = True
        url_after = str(meta.get("url_after") or _url_safe(page))
        if outcome in _AMBIGUOUS_OUTCOMES or outcome == "submit_error":
            if not still_on_same_detail_after_submit(url_before, url_after):
                meta["navigation_outcome"] = "returned_to_list"
    elif not meta.get("left_detail_context"):
        url_after = str(meta.get("url_after") or _url_safe(page))
        if submit_left_detail_context(url_before, url_after, list_anchor=list_anchor):
            meta["left_detail_context"] = True
            if outcome in _AMBIGUOUS_OUTCOMES:
                meta["navigation_outcome"] = "returned_to_list"
        elif not _page_alive(page):
            usable = find_usable_context_pages(page, list_anchor)
            if usable:
                pick = usable[0]
                for p in usable:
                    if not is_detail_submission_url(_url_safe(p)):
                        pick = p
                        break
                page = pick
                try:
                    page.bring_to_front()
                except Exception:
                    pass
                meta["left_detail_context"] = True
                meta["navigation_outcome"] = "returned_to_list"
                meta["url_after"] = _url_safe(page)
                meta["detail_tab_closed"] = True
        elif _page_usable(page) and not is_detail_submission_url(_url_safe(page)):
            meta["left_detail_context"] = True
            if outcome in _AMBIGUOUS_OUTCOMES:
                meta["navigation_outcome"] = "returned_to_list"

    if meta.get("submit_click_ok"):
        dispatch_ok = submit_dispatch_should_succeed(meta)
    message = None
    if dispatch_ok and outcome in _AMBIGUOUS_OUTCOMES.union({"submit_error"}):
        message = f"提交后已离开详情上下文 ({str(meta.get('url_after') or '')[:80]})"
    return SubmitFinalizeResult(page, meta, dispatch_ok, message)


@dataclass
class SubmitPostVerdict:
    """本地提交后校验结论; step_ok=None 表示交 LLM."""

    step_ok: Optional[bool]
    reason: str = ""
    page: Any = None
    meta: Optional[dict[str, Any]] = None


def _page_has_submit_error(page: Any, dom_summary: Optional[str]) -> bool:
    """页面是否显示提交失败文案."""
    text = (dom_summary or "").strip()
    if not text and _page_usable(page):
        text = _read_body_safe(page)
    return bool(text) and _body_has_submit_error(text)


def evaluate_submit_post_check(
    intent: str,
    dispatch_ok: bool,
    dispatch_meta: Optional[dict[str, Any]],
    page: Any,
    dom_summary: Optional[str],
    *,
    list_anchor: Any = None,
    api_context: Optional[dict[str, Any]] = None,
) -> SubmitPostVerdict:
    """提交类步骤后校验 — 通用三阶段: 恢复 tab → 结构化事实 → 本地 verdict."""
    if not is_submit_intent(intent):
        return SubmitPostVerdict(step_ok=None)

    meta = dict(dispatch_meta or {})
    url_before = str(meta.get("url_before") or "")
    outcome = str(meta.get("navigation_outcome") or "")

    if is_detail_submission_url(url_before) and outcome not in (
        "resource_id_changed", "route_changed", "list_empty",
    ):
        fin = pick_surviving_tab_after_detail_close(
            page, url_before=url_before, list_anchor=list_anchor,
        )
        page, recovered, url_after, left_detail = fin
        meta["url_after"] = url_after or str(meta.get("url_after") or "")
        if left_detail:
            meta["left_detail_context"] = True
        if recovered:
            meta["recovered"] = True
        if not _page_alive(page) and is_detail_submission_url(url_before):
            meta["detail_tab_closed"] = True

    facts = build_outcome_facts(meta, dom_summary=dom_summary, api_context=api_context)
    meta["submit_context"] = facts.context.value

    local = evaluate_submit_outcome(
        facts, dom_summary=dom_summary, dispatch_ok=dispatch_ok,
    )
    if local is not None:
        ok, reason = local
        return SubmitPostVerdict(step_ok=ok, reason=reason, page=page, meta=meta)

    return SubmitPostVerdict(step_ok=None, page=page, meta=meta)
