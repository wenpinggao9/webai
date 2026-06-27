"""upload 动作: 定位隐藏的 input[type=file], 不走触发按钮."""
from __future__ import annotations

import re
from typing import Any, Optional

from .playwright_api import info_key, normalize_info

# 弹窗/上传区优先, 最后全局 fallback
_UPLOAD_FILE_INPUT_SELECTORS: tuple[str, ...] = (
    'section:has-text("视频上传") input[type="file"]',
    '.el-dialog:visible input[type="file"]',
    '.ant-modal:visible input[type="file"]',
    '.el-upload input[type="file"]',
    '.ant-upload input[type="file"]',
    'input[type="file"]',
)


def is_unsafe_upload_selector(info: dict) -> bool:
    """upload 动作误命中 button/非 file input 时拒绝使用该选择器."""
    spec = normalize_info(info)
    method = str(spec.get("method") or "").lower()
    sel = info_key(info).lower()
    if method == "role" and str(spec.get("role") or "").lower() == "button":
        return True
    if "button" in sel and "input" not in sel and "file" not in sel:
        return True
    if method == "css" and sel and "file" not in sel:
        return True
    return False


def _scope_selector_from_intent(intent: str) -> Optional[str]:
    """从 intent 提取弹窗/区域关键词, 生成 scoped file input 选择器."""
    for pattern in (r"「([^」]+)」", r"'([^']+)'", r'"([^"]+)"'):
        m = re.search(pattern, intent or "")
        if not m:
            continue
        label = (m.group(1) or "").strip()
        if not label or len(label) > 40:
            continue
        if any(k in label for k in ("上传", "视频", "文件", "附件", "资源")):
            safe = label.replace('"', '\\"')
            return f'section:has-text("{safe}") input[type="file"]'
    return None


def try_resolve_upload_file_input(
    page: Any,
    intent: str = "",
    exclude: Optional[set[str]] = None,
) -> Optional[dict]:
    """在页面/弹窗内查找 input[type=file]; 命中返回 locator_info dict."""
    excl = exclude or set()
    candidates: list[str] = []
    scoped = _scope_selector_from_intent(intent)
    if scoped:
        candidates.append(scoped)
    candidates.extend(_UPLOAD_FILE_INPUT_SELECTORS)

    seen: set[str] = set()
    for sel in candidates:
        if sel in seen or sel in excl:
            continue
        seen.add(sel)
        try:
            loc = page.locator(sel)
            if loc.count() <= 0:
                continue
            # file input 常为 hidden; 只校验 DOM 存在
            info = normalize_info({
                "method": "css",
                "selector": sel,
                "nth": 0,
            })
            return {**info, "_source": "file_input"}
        except Exception:
            continue
    return None
