"""后校验 step_ok 与 reason 一致性纠偏."""
from __future__ import annotations

from core.runtime.execution.post_check import (
    _check_select_trigger_expand,
    _reconcile_post_check_step_ok,
)


def test_reconcile_when_reason_says_success_but_step_ok_false():
    reason = (
        "所以审核行为下拉框已成功展开。"
    )
    assert _reconcile_post_check_step_ok(False, reason, True) is True


def test_reconcile_keeps_false_when_dispatch_failed():
    assert _reconcile_post_check_step_ok(False, "已成功展开", False) is False


def test_select_trigger_expand_detects_visible_options():
    dom = (
        '[1058] div role=listbox id=submitType_list\n'
        '[1062] div ant-select-item-option 举报/放弃\n'
    )
    result = _check_select_trigger_expand(
        "在筛选区点击'审核行为'下拉框",
        True,
        dom,
    )
    assert result is not None
    assert result.step_ok is True
