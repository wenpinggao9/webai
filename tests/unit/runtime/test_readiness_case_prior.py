"""跨块 prior_actions + radio recovery 去重."""
from __future__ import annotations

from types import SimpleNamespace

from core.pipeline.planning import PlannedAction
from core.runtime.execution.deterministic_recovery import (
    filter_redundant_radio_recovery,
    resolve_expected_radio_label,
)
from core.runtime.execution.runner import PlaywrightRunner


def _click(intent: str, *, recovery: bool = False) -> PlannedAction:
    return PlannedAction(
        type="click",
        intent=intent,
        value=None,
        is_recovery=recovery,
    )


def test_resolve_expected_radio_prefers_latest_prior_click():
    prior = [
        _click("选择「水印题且可做」"),
        _click("点击「学科」下拉框，并修改为「物理」"),
        _click("选择「题目无任何问题」"),
    ]
    label = resolve_expected_radio_label(
        last_click_label=None,
        api_context={},
        prior_actions=prior,
        case_steps=["选择「水印题且可做」", "选择「题目无任何问题」"],
        case_notes=[],
    )
    assert label == "题目无任何问题"


def test_filter_redundant_radio_recovery_drops_checked():
    page = SimpleNamespace(
        evaluate=lambda _js, label: {"checked": label == "题目无任何问题", "found": True},
    )
    recovery = [
        PlannedAction(
            type="click",
            intent="选择审核原因'题目无任何问题'单选项",
            value=None,
        ),
        PlannedAction(type="click", intent="关闭弹窗", value=None),
    ]
    prior = [_click("选择「题目无任何问题」")]
    kept = filter_redundant_radio_recovery(
        recovery,
        page,
        prior_actions=prior,
        next_action=PlannedAction(type="click", intent="点击'提交'按钮", value=None),
        case_steps=[],
        case_notes=[],
    )
    assert len(kept) == 1
    assert kept[0].intent == "关闭弹窗"


def test_runner_effective_prior_merges_case_and_block():
    runner = PlaywrightRunner.__new__(PlaywrightRunner)
    runner._case_prior_actions = [_click("块5: 选择「题目无任何问题」")]
    block = [
        _click("块6: 其他操作"),
        PlannedAction(type="click", intent="点击'提交'按钮", value=None),
    ]
    prior = runner._effective_prior_actions(block, 1)
    assert len(prior) == 2
    assert "题目无任何问题" in prior[0].intent
    assert prior[1].intent == "块6: 其他操作"
