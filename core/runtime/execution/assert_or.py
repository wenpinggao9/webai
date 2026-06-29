"""「或」语义断言 —— 预期多分支时任一支满足即通过."""
from __future__ import annotations

import re
from typing import Any, Optional

from .page_morphology import (
    MainContentMorphology,
    detect_main_content_morphology,
    main_content_contains,
    token_only_in_nav,
)
from .post_submit_eval import (
    eval_submit_expect,
    infer_expect_from_text,
)

_OR_INTENT_RE = re.compile(r"否则|有的话|没有.{0,24}则|任一|任意一种")
# 分支 intent 语义 (来自用例描述, 非 DOM 业务字段)
_LIST_BRANCH_RE = re.compile(
    r"列表|list|回到|返回|回.*页|领.*页|索引页|一览",
    re.I,
)
_DETAIL_BRANCH_RE = re.compile(
    r"详情|detail|下一条|另一条|下一个|单条|记录页|明细",
    re.I,
)


def is_or_assert(action: Any) -> bool:
    """是否为多分支「或」断言.

    注意: 选项文案本身可含「或」(如「题目不完整或题干残缺」), 不是逻辑分支.
    """
    extras = getattr(action, "extras", None) or {}
    if extras.get("any_of") or extras.get("or_group"):
        return True
    if extras.get("branches"):
        return True
    value = (getattr(action, "value", None) or "").strip()
    intent = getattr(action, "intent", None) or ""
    if value and "或" in value:
        if value in intent or re.search(r"(包含|含)", intent):
            return False
    if _OR_INTENT_RE.search(intent):
        return True
    if "或" in intent:
        if re.search(r"(包含|含|选项包括|包括)", intent):
            return False
        return True
    return False


def _resolve_or_page_url(
    page: Any,
    page_url: str = "",
    dispatch_meta: Optional[dict[str, Any]] = None,
) -> str:
    try:
        live = (getattr(page, "url", None) or "").lower()
        if live:
            return live
    except Exception:
        pass
    for cand in (page_url, str((dispatch_meta or {}).get("url_after") or "")):
        if cand:
            return cand.lower()
    return ""


def _branch_wants_list(intent: str, branch_value: str) -> bool:
    if _LIST_BRANCH_RE.search(intent):
        return True
    if branch_value and not _DETAIL_BRANCH_RE.search(intent):
        return bool(_LIST_BRANCH_RE.search(branch_value))
    return False


def _branch_wants_form_detail(intent: str) -> bool:
    return bool(_DETAIL_BRANCH_RE.search(intent))


def _layout_hit_for_branch(
    intent: str,
    branch_value: str,
    morph: MainContentMorphology,
) -> Optional[tuple[bool, str]]:
    """结构层: table_dominant / form_dominant (无业务词). mixed 返回 None 交语义层."""
    want_list = _branch_wants_list(intent, branch_value)
    want_form = _branch_wants_form_detail(intent)

    if want_list and morph.is_table_dominant:
        return True, "主内容区为数据表主导布局 (table_dominant)"
    if want_list and morph.is_form_dominant:
        return False, "主内容区仍为表单主导布局 (form_dominant)"
    if want_form and morph.is_form_dominant:
        return True, "主内容区为表单/单记录主导布局 (form_dominant)"
    if want_form and morph.is_table_dominant:
        return False, "主内容区仍为数据表主导布局 (table_dominant)"
    return None


def _eval_branch_with_facts(
    branch_intent: str,
    morph: MainContentMorphology,
    facts: Any,
    url: str,
) -> Optional[tuple[bool, str]]:
    exp = infer_expect_from_text(branch_intent)
    if not exp:
        return None
    if exp == "navigated_away":
        if morph.is_table_dominant:
            return True, "主内容区已切换为数据表主导布局"
        if morph.is_form_dominant:
            return False, "主内容区仍为表单主导布局"
        return None
    if exp == "entity_changed":
        if morph.is_form_dominant:
            if facts and getattr(facts, "entity_changed", False):
                return True, (
                    f"主内容区表单布局且实体已切换 "
                    f"({facts.entity_id_before} → {facts.entity_id_after})"
                )
            return True, "主内容区为表单/单记录主导布局"
        if morph.is_table_dominant:
            return False, "主内容区为数据表布局, 非单记录表单"
        return None
    ok, msg = eval_submit_expect(exp, facts, url)
    if ok and exp in ("navigated_away", "entity_changed"):
        return None
    if ok:
        return True, msg
    return False, msg


def try_or_branches(
    page: Any,
    branches: list[Any],
    body_text: str,
    *,
    dispatch_meta: Optional[dict[str, Any]] = None,
    page_url: str = "",
    live_facts: Any = None,
) -> Optional[tuple[bool, str]]:
    """逐支尝试: 主区结构布局 → 主区字面量 → 提交事实; 均未决则返回 None 交语义断言."""
    url = _resolve_or_page_url(page, page_url, dispatch_meta)
    facts = live_facts
    morph = detect_main_content_morphology(page)

    for i, raw in enumerate(branches):
        if not isinstance(raw, dict):
            continue
        branch_intent = str(raw.get("intent") or raw.get("desc") or "").strip()
        branch_value = str(raw.get("value") or "").strip()
        label = branch_intent or branch_value or f"分支{i + 1}"

        layout_hit = _layout_hit_for_branch(branch_intent, branch_value, morph)
        if layout_hit is not None:
            ok, detail = layout_hit
            if ok:
                return True, f"或断言(分支{i + 1}): {detail} ({label})"
            if _branch_wants_list(branch_intent, branch_value) or _branch_wants_form_detail(branch_intent):
                continue

        if branch_value and not token_only_in_nav(morph, branch_value):
            if main_content_contains(page, branch_value, morphology=morph):
                return True, (
                    f"或断言(分支{i + 1}): 主内容区含 {branch_value!r} ({label})"
                )

        if facts is not None:
            fact_hit = _eval_branch_with_facts(branch_intent, morph, facts, url)
            if fact_hit is not None:
                ok, msg = fact_hit
                if ok:
                    return True, f"或断言(分支{i + 1}): {msg} ({label})"
                if exp := infer_expect_from_text(branch_intent):
                    if exp in ("navigated_away", "entity_changed"):
                        continue

        hit = try_or_heuristic(
            page, branch_intent,
            dispatch_meta=dispatch_meta,
            page_url=url,
            body_text=body_text,
            live_facts=facts,
            morphology=morph,
            branch_value=branch_value,
        )
        if hit is not None and hit[0]:
            detail = hit[1]
            if not detail.startswith("或断言"):
                detail = f"或断言(分支{i + 1}): {detail}"
            return True, detail
    return None


def combined_or_intent(action: Any) -> str:
    """合并 intent 与 extras.branches 供语义断言使用."""
    intent = getattr(action, "intent", None) or ""
    branches = (getattr(action, "extras", None) or {}).get("branches") or []
    parts = [intent] if intent else []
    for b in branches:
        if isinstance(b, dict):
            t = str(b.get("intent") or b.get("desc") or "").strip()
            if t:
                parts.append(t)
    return "；".join(parts) if parts else intent


def try_or_heuristic(
    page: Any,
    intent: str,
    *,
    dispatch_meta: Optional[dict[str, Any]] = None,
    page_url: str = "",
    body_text: str = "",
    live_facts: Any = None,
    morphology: MainContentMorphology | None = None,
    branch_value: str = "",
) -> Optional[tuple[bool, str]]:
    """结构层快速判定; mixed/未决返回 None."""
    if not intent:
        return None
    morph = morphology or detect_main_content_morphology(page)
    facts = live_facts
    url = _resolve_or_page_url(page, page_url, dispatch_meta)

    layout_hit = _layout_hit_for_branch(intent, branch_value, morph)
    if layout_hit is not None and layout_hit[0]:
        return True, f"或断言(启发式): {layout_hit[1]}"

    if facts is not None:
        fact_hit = _eval_branch_with_facts(intent, morph, facts, url)
        if fact_hit is not None and fact_hit[0]:
            return True, f"或断言(启发式): {fact_hit[1]}"

    return None
