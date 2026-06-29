"""规划标记 extras.semantic → 执行层跳过字面量, 走 LLM."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.execution.assert_scope import action_prefers_semantic_assert
from core.execution.dispatcher import ActionDispatcher
from core.planning import PlannedAction


def test_action_prefers_semantic_assert_flag():
    assert action_prefers_semantic_assert(
        PlannedAction(type="assert_text", intent="x", extras={"semantic": True})
    )
    assert action_prefers_semantic_assert(
        PlannedAction(type="assert_text", intent="x", extras={"assert_mode": "semantic"})
    )
    assert not action_prefers_semantic_assert(
        PlannedAction(type="assert_text", intent="x", value="提交")
    )


def test_assert_text_skips_literal_when_planner_marks_semantic(monkeypatch):
    resolver = MagicMock()
    resolver._framework_selectors = None
    d = ActionDispatcher(MagicMock(), resolver, console=MagicMock())

    items = [{"tag": "nav", "text": "详情", "in_nav": True}]
    programmatic_called = {"v": False}
    semantic_called = {"v": False}

    def fake_get_state(action=None, *, force_refresh=False):
        from core.dom.semantic_dom import compact_dom_lines
        return True, items, compact_dom_lines(items), ""

    def fake_programmatic(*a, **k):
        programmatic_called["v"] = True
        return True, "断言: 页面含 '详情'"

    def fake_semantic(*a, **k):
        semantic_called["v"] = True
        return True, "语义断言: 已进入任务详情页"

    monkeypatch.setattr(d, "_get_page_state_for_assert", fake_get_state)
    monkeypatch.setattr(d, "_assert_text_programmatic", fake_programmatic)
    monkeypatch.setattr(d, "_semantic_assert", fake_semantic)
    monkeypatch.setattr(d, "_should_semantic_fallback", lambda _s: True)

    action = PlannedAction(
        type="assert_text",
        intent="验证页面自动加载下一个任务的详情页",
        value="详情",
        extras={"semantic": True},
    )
    ok, msg = d._assert_text(action)
    assert ok is True
    assert not programmatic_called["v"]
    assert semantic_called["v"]
    assert "语义断言" in msg
