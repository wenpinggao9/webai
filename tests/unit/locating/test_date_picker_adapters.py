"""date_picker_adapters 单元测试."""
from __future__ import annotations

from core.locating.date_picker_adapters import (
    build_date_picker_candidates,
    build_panel_date_candidates,
    detect_date_picker_kind,
    xpath_day_in_month_table,
)
from core.locating.skill_dom_helpers import build_date_picker_selector


def _check_history_calendar_dom() -> list[dict]:
    items: list[dict] = []
    items.append({"tag": "th", "text": "2026年Jun"})
    for d in range(1, 32):
        items.append({"tag": "td", "text": str(d)})
        items.append({"tag": "div", "text": str(d)})
    items.append({"tag": "th", "text": "2026年Jul"})
    for d in range(1, 32):
        items.append({"tag": "td", "text": str(d)})
    return items


def test_detect_generic_calendar_without_ant_class():
    dom = _check_history_calendar_dom()
    assert detect_date_picker_kind(dom) == "generic"


def test_month_header_xpath_first_for_panel():
    intent = "在'审核时间'日期面板中选择开始日期 2026-06-22"
    dom = _check_history_calendar_dom()
    cands = build_panel_date_candidates(dom, "2026-06-22", intent, "generic")
    assert cands[0] == xpath_day_in_month_table(2026, 6, 22)
    assert "Jun" in cands[0] or "2026" in cands[0]
    assert "22" in cands[0]


def test_build_date_picker_selector_delegates_to_adapters():
    dom = [
        {"tag": "label", "text": "审核时间"},
        {"tag": "input", "id": "submitTimeRange", "placeholder": "开始日期"},
    ]
    r = build_date_picker_selector(dom, "在筛选区点击'审核时间'日期选择框")
    assert r["candidates"][0] == "input#submitTimeRange"

    cal = _check_history_calendar_dom()
    r2 = build_date_picker_selector(cal, "在'审核时间'日期面板中选择开始日期 2026-06-22")
    assert r2["selector"]
    assert "22" in r2["selector"]
    assert "审核时间" not in r2["selector"]


def test_end_date_uses_target_month_not_second_panel_only():
    dom = _check_history_calendar_dom()
    intent = "在'审核时间'日期面板中选择结束日期 2026-06-23"
    result = build_date_picker_candidates(dom, intent)
    assert any("23" in c for c in result["candidates"])
    first = result["candidates"][0]
    assert "Jun" in first or "2026" in first


def test_invoke_build_helper_accepts_extracted_target_text():
    """L3 会传入 target_text; 日期 skill 不得因多参静默失败."""
    from core.locating.skill_resolver import _invoke_build_helper

    dom = _check_history_calendar_dom()
    intent = "在'审核时间'日期面板中选择开始日期 2026-06-22"
    result = _invoke_build_helper("build_date_picker_selector", dom, intent, "审核时间")
    assert result is not None
    assert result.get("selector")
    assert "22" in result["selector"]
