"""DOM 采集: 组件库单选/多选包装节点补充 type/role 元数据."""
from __future__ import annotations

from core.understanding.dom.semantic_dom import format_indexed_dom_line
from core.understanding.dom.v3_bridge import enrich_choice_control_metadata


def test_enrich_ant_radio_wrapper_metadata():
    items = [{
        "tag": "label",
        "class": "ant-radio-wrapper",
        "text": "选项 A",
        "role": "",
        "type": "",
    }]
    enrich_choice_control_metadata(items)
    assert items[0]["role"] == "radio"
    assert items[0]["type"] == "radio"


def test_enrich_preserves_native_radio_type():
    items = [{"tag": "input", "type": "radio", "text": "", "role": "", "class": ""}]
    enrich_choice_control_metadata(items)
    assert items[0]["role"] == "radio"
    assert items[0]["type"] == "radio"


def test_enrich_ant_checkbox_wrapper_metadata():
    items = [{
        "tag": "label",
        "class": "ant-checkbox-wrapper",
        "text": "选项 B",
        "role": "",
        "type": "",
    }]
    enrich_choice_control_metadata(items)
    assert items[0]["role"] == "checkbox"
    assert items[0]["type"] == "checkbox"


def test_indexed_dom_line_shows_radio_type():
    item = {
        "tag": "label",
        "class": "ant-radio-wrapper",
        "text": "选项 A",
        "role": "radio",
        "type": "radio",
        "in_form": True,
    }
    line = format_indexed_dom_line(0, item)
    assert 'type="radio"' in line
    assert 'role="radio"' in line
