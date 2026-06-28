"""submit_outcome 通用提交后校验模型."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.execution.popup_recovery import needs_popup_recovery
from core.execution.post_check import PostCheckResult
from core.execution.submit_outcome import (
    SubmitContextKind,
    body_has_list_empty_state,
    build_outcome_facts,
    capture_submit_snapshot,
    classify_submit_context,
    detect_list_embed_progress,
    evaluate_submit_outcome,
)
from core.execution.submit_post_verify import evaluate_submit_post_check
from core.execution.dispatcher import ActionDispatcher

TASKLIST = "https://www-gwp11-bc.suanshubang.com/video/tasklist?vvp=%2Fvvp%2Fv3%2Ftasklist"
DETAIL = "https://www-gwp11-bc.suanshubang.com/video/detail/?uniqId=146482774"


def test_classify_detail_url():
    assert classify_submit_context(DETAIL) == SubmitContextKind.DETAIL_URL


def test_classify_list_embed_from_dom():
    dom = "回收倒计时 题目ID:47841257 任务ID:146789315 提交任务"
    assert classify_submit_context(TASKLIST, flat_text=dom) == SubmitContextKind.LIST_EMBED


def test_detect_list_embed_empty():
    assert detect_list_embed_progress("暂无题目，请去任务中心领题") == "list_empty"


def test_detect_list_embed_entity_switch():
    before = "47841257"
    after_dom = "题目ID:47849999 题干"
    assert detect_list_embed_progress(after_dom, entity_before=before) == "resource_id_changed"


def test_evaluate_submit_outcome_list_empty():
    facts = build_outcome_facts(
        {"url_before": TASKLIST, "navigation_outcome": "list_empty", "submit_context": "list_embed"},
        dom_summary="暂无题目 请去任务中心领题",
    )
    result = evaluate_submit_outcome(facts, dom_summary="暂无题目")
    assert result == (True, "提交后进入空态(无剩余待办)")


def test_evaluate_submit_post_check_list_embed_short_circuit():
    verdict = evaluate_submit_post_check(
        "点击'提交任务'",
        dispatch_ok=True,
        dispatch_meta={
            "url_before": TASKLIST,
            "navigation_outcome": "list_empty",
            "submit_context": "list_embed",
        },
        page=MagicMock(),
        dom_summary="暂无题目 请去任务中心领题",
    )
    assert verdict.step_ok is True
    assert "空态" in verdict.reason


def test_evaluate_submit_post_check_entity_changed():
    verdict = evaluate_submit_post_check(
        "点击'提交任务'",
        dispatch_ok=True,
        dispatch_meta={
            "url_before": TASKLIST,
            "url_after": TASKLIST,
            "navigation_outcome": "resource_id_changed",
            "entity_id_before": "47841257",
            "entity_id_after": "47849999",
            "submit_context": "list_embed",
        },
        page=MagicMock(),
        dom_summary="题目ID:47849999",
    )
    assert verdict.step_ok is True


def test_capture_snapshot_from_dom():
    snap = capture_submit_snapshot(
        url=TASKLIST,
        flat_text="题目 ID:123 提交任务",
    )
    assert snap.context == SubmitContextKind.LIST_EMBED
    assert snap.entity_id == "123"


def test_popup_recovery_negated_dialog():
    post = PostCheckResult(
        step_ok=False,
        reason="URL 未变, 未出现任何弹窗/确认对话框, 提交任务按钮仍存在",
    )
    assert needs_popup_recovery(post, dispatch_ok=True) is False


def test_popup_recovery_real_block():
    post = PostCheckResult(step_ok=False, reason="点击被弹窗遮挡, 需勾选红线协议")
    assert needs_popup_recovery(post, dispatch_ok=True) is True


def test_should_wait_submit_on_tasklist():
    d = ActionDispatcher.__new__(ActionDispatcher)
    assert d._should_wait_post_submit_navigation(TASKLIST, MagicMock(), "点击'提交任务'") is True
    assert d._should_wait_post_submit_navigation(TASKLIST, MagicMock(), "点击确认") is False


def test_body_has_list_empty_state():
    assert body_has_list_empty_state("请去任务中心领题") is True
    assert body_has_list_empty_state("题目ID:1") is False
