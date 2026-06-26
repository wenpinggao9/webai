"""build_date_picker_selector 单元测试."""
from __future__ import annotations

from core.locating.skill_dom_helpers import (
    _detect_date_panel_from_dom,
    _intent_is_panel_date_selection,
    build_date_picker_selector,
)


def _calendar_dom() -> list[dict]:
    items: list[dict] = []
    for d in range(1, 32):
        items.append({"tag": "td", "text": str(d), "class": "available"})
    items.insert(0, {"tag": "th", "text": "2026年Jun", "class": "header"})
    items.append({"tag": "th", "text": "2026年Jul", "class": "header"})
    for d in range(1, 32):
        items.append({"tag": "td", "text": str(d), "class": "available"})
    return items


def test_panel_intent_without_ant_class_still_builds_candidates():
    dom = _calendar_dom()
    assert _detect_date_panel_from_dom(dom)
    assert _intent_is_panel_date_selection("在日期面板中选择 2026-06-22")

    result = build_date_picker_selector(dom, "在日期面板中选择 2026-06-22")
    assert result["selector"]
    assert any("22" in c for c in result["candidates"])
    assert any("Jun" in c or "2026" in c for c in result["candidates"])


def test_trigger_intent_uses_placeholder_for_audit_time_field():
    dom = [
        {"tag": "label", "text": "审核时间", "class": ""},
        {"tag": "input", "id": "submitTimeRange", "placeholder": "开始日期", "class": ""},
    ]
    result = build_date_picker_selector(dom, "在筛选区点击'审核时间'日期选择框")
    assert result["selector"]
    assert any("开始日期" in c or "submitTimeRange" in c for c in result["candidates"])


def test_semantic_calendar_prefers_td_for_day_cell():
    dom = [
        {"tag": "th", "text": "2026年Jun"},
        {"tag": "td", "text": "21"},
        {"tag": "td", "text": "22"},
        {"tag": "div", "text": "22"},
        {"tag": "th", "text": "2026年Jul"},
    ]
    result = build_date_picker_selector(dom, "在日期面板中选择 2026-06-22")
    assert result["candidates"][0].startswith("td:") or result["candidates"][0].startswith("(//")
