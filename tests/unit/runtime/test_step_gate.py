"""步骤门控: 基于 navigation_outcome / 页面状态, 不依赖 intent 文案."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.pipeline.planning import PlannedAction
from core.runtime.execution.nav_progress import navigation_outcome_requires_readiness
from core.runtime.execution.post_check import check_navigation_click_success
from core.runtime.execution.popup_recovery import page_has_blocking_dialog
from core.runtime.readiness.pre_check import should_skip_readiness_after_post_ok


def test_navigation_outcome_requires_readiness_for_route_change():
    assert navigation_outcome_requires_readiness("route_changed") is True
    assert navigation_outcome_requires_readiness("resource_id_changed") is True
    assert navigation_outcome_requires_readiness("") is False
    assert navigation_outcome_requires_readiness(None) is False


def test_nav_shortcut_blocked_for_route_changed_regardless_of_intent():
    """列表/路由切换: 不因 intent 含「任务」而走 URL 短路."""
    ok = check_navigation_click_success(
        "点击侧栏菜单'任务中心'进入任务中心页面",
        "https://example.com/video/taskindex",
        True,
        "click",
        {"navigation_outcome": "route_changed"},
        page=None,
    )
    assert ok is None


def test_nav_shortcut_allowed_for_entity_change_without_dialog():
    ok = check_navigation_click_success(
        "任意文案",
        "https://example.com/detail?id=1",
        True,
        "click",
        {"navigation_outcome": "resource_id_changed"},
        page=None,
    )
    assert ok is True


def test_nav_shortcut_blocked_when_modal_visible():
    page = MagicMock()
    page.locator.return_value.count.return_value = 1
    ok = check_navigation_click_success(
        "任意文案",
        "https://example.com/detail?id=1",
        True,
        "click",
        {"navigation_outcome": "resource_id_changed"},
        page=page,
    )
    assert ok is None
    assert page_has_blocking_dialog(page) is True


def test_skip_readiness_after_post_ok_when_prev_route_changed():
    action = PlannedAction(type="click", intent="在筛选区点击'学科'下拉框")
    assert should_skip_readiness_after_post_ok(
        action,
        True,
        prev_nav_outcome="route_changed",
    ) is False


def test_skip_readiness_after_post_ok_for_chained_dropdown():
    action = PlannedAction(type="click", intent="在下拉选项中点击'大学化学'")
    assert should_skip_readiness_after_post_ok(
        action,
        True,
        prev_nav_outcome=None,
    ) is True
