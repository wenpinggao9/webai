"""筛选框清除 × 后校验 — 通用信号, 无业务文案."""
from __future__ import annotations

from core.runtime.execution.post_check import (
    PostCheckResult,
    _check_select_clear_click,
    _dom_select_clear_still_effective_blocker,
    _select_clear_resolve_hint,
)


def test_resolve_hint_with_field_label():
    hint = _select_clear_resolve_hint("来源")
    assert "来源" in hint
    assert "ant-select-clear" in hint


def test_resolve_hint_without_field_uses_generic():
    hint = _select_clear_resolve_hint(None)
    assert "ant-select-clear" in hint
    assert "来源" not in hint


def test_clear_blocker_detects_clear_icon_plus_selection_tag():
    dom = (
        "[10] span class=ant-select-selection-item 待申诉\n"
        "[13] span class=anticon-close-circle close-circle\n"
    )
    assert _dom_select_clear_still_effective_blocker(dom) is True


def test_clear_blocker_ignores_business_text_without_structure():
    dom = "表格列显示待申诉状态"
    assert _dom_select_clear_still_effective_blocker(dom) is False


def test_check_select_clear_fails_on_label_click():
    result = _check_select_clear_click(
        "点击'学科'筛选框中的清除'×'",
        dispatch_ok=True,
        dispatch_msg='实际目标: <label title="学科">学科</label>',
        dom="",
    )
    assert isinstance(result, PostCheckResult)
    assert result.step_ok is False
    assert "label" in result.reason
    assert "学科" in result.resolve_hint


def test_check_select_clear_fails_when_clear_and_tag_remain():
    result = _check_select_clear_click(
        "点击'状态'筛选框中的清除'×'",
        dispatch_ok=True,
        dispatch_msg="实际目标: <span class=ant-select-clear>",
        dom="[1] ant-select-selection-item [2] close-circle",
    )
    assert result is not None
    assert result.step_ok is False
    assert "未生效" in result.reason
