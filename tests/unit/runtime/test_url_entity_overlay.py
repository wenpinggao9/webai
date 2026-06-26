"""URL 实体 ID 同步到上下文（框架通用，不绑定业务字段名）."""
from __future__ import annotations

from core.runtime.execution.entity_discover import overlay_url_entity_context
from core.runtime.execution.session_ops import sync_url_context


class _Page:
    def __init__(self, url: str) -> None:
        self.url = url


def test_overlay_url_entity_updates_matching_query_keys():
    page = _Page("https://host/app/detail/?uniqId=146713300")
    ctx = {"uniqId": "146713297", "orderId1001": "146713238"}
    overlay_url_entity_context(page, ctx)
    assert ctx["uniqId"] == "146713300"
    assert ctx["orderId1001"] == "146713238"


def test_overlay_no_op_when_url_has_no_entity_params():
    page = _Page("https://host/app/list")
    ctx = {"uniqId": "146713297"}
    overlay_url_entity_context(page, ctx)
    assert ctx["uniqId"] == "146713297"


def test_page_capture_maps_url_key_to_context_name():
    page = _Page("https://host/video/detail/?uniqId=146713300")
    ctx = {"workId": "146713297", "uniqId": "146713297"}
    sync_url_context(
        page,
        ctx,
        page_capture={"workId": {"from": "url_query", "key": "uniqId"}},
    )
    assert ctx["uniqId"] == "146713300"
    assert ctx["workId"] == "146713300"
