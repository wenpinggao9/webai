"""date_picker_guard 与 build_date_picker_selector 单元测试."""
from __future__ import annotations

from core.locating.date_picker_guard import (
    extract_date_field_label,
    is_ambiguous_range_placeholder_name,
    is_bare_range_placeholder_selector,
    is_strong_date_picker_selector,
    is_weak_date_label_text_selector,
    is_weak_date_placeholder_for_intent,
)
from core.locating.skill_dom_helpers import build_date_picker_selector


def test_ambiguous_placeholder_multilingual():
    assert is_ambiguous_range_placeholder_name("开始日期")
    assert is_ambiguous_range_placeholder_name("End date")
    assert not is_ambiguous_range_placeholder_name("工单ID精确搜索")


def test_bare_placeholder_weak_when_intent_has_field():
    sel = 'placeholder:"开始日期"'
    assert is_bare_range_placeholder_selector(sel)
    intent = "在筛选区点击'审核时间'日期选择框"
    assert is_weak_date_placeholder_for_intent(sel, intent)
    assert not is_weak_date_placeholder_for_intent(sel, "点击日期")


def test_label_text_weak_for_date_trigger():
    intent = "在筛选区点击'审核时间'日期选择框"
    assert is_weak_date_label_text_selector('text="审核时间"', intent)
    assert is_strong_date_picker_selector("input#submitTimeRange")


def test_extract_field_from_panel_intent():
    intent = "在'审核时间'日期面板中选择开始日期 2026-06-22"
    assert extract_date_field_label(intent) == "审核时间"


def test_panel_intent_builds_day_cell_not_label():
    dom = [
        {"tag": "th", "text": "2026年Jun"},
        {"tag": "td", "text": "21"},
        {"tag": "td", "text": "22"},
        {"tag": "th", "text": "2026年Jul"},
        {"tag": "td", "text": "22"},
        {"tag": "td", "text": "23"},
    ]
    intent = "在'审核时间'日期面板中选择开始日期 2026-06-22"
    result = build_date_picker_selector(dom, intent)
    assert result["selector"]
    assert result["selector"].startswith("(//th")
    assert "22" in result["selector"]

    dom = [
        {"tag": "label", "text": "审核时间", "class": ""},
        {"tag": "input", "id": "submitTimeRange", "placeholder": "开始日期", "class": ""},
    ]
    result = build_date_picker_selector(dom, "在筛选区点击'审核时间'日期选择框")
    assert result["selector"]
    first = result["candidates"][0]
    assert (
        first.startswith("input#")
        or "label" in first
        or "@for" in first
    )
    assert result["candidates"][-1].startswith("(//input[contains(@placeholder")
