"""upload file input 定位."""
from __future__ import annotations

from core.locating.playwright_api import info_key, normalize_info
from core.locating.upload_resolver import (
    is_unsafe_upload_selector,
    try_resolve_upload_file_input,
)


def test_unsafe_upload_rejects_button_role():
    info = normalize_info({"method": "role", "role": "button", "name": "上传视频文件"})
    assert is_unsafe_upload_selector(info) is True


def test_unsafe_upload_accepts_file_input_css():
    info = normalize_info({"method": "css", "selector": 'input[type="file"]'})
    assert is_unsafe_upload_selector(info) is False


def test_scope_selector_from_intent():
    from core.locating.upload_resolver import _scope_selector_from_intent

    sel = _scope_selector_from_intent("在「视频上传」弹窗中选择文件")
    assert sel is not None
    assert "视频上传" in sel
    assert "file" in sel


def test_try_resolve_upload_on_mock_page():
    class _Loc:
        def __init__(self, n: int):
            self._n = n

        def count(self):
            return self._n

        @property
        def first(self):
            return self

    class _Page:
        def locator(self, sel: str):
            if 'input[type="file"]' in sel:
                return _Loc(1)
            return _Loc(0)

    info = try_resolve_upload_file_input(_Page(), "上传 vip2.mp4")
    assert info is not None
    assert 'input[type="file"]' in info_key(info)
