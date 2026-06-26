"""日期控件 selector 强弱判定 — 全业务通用, 不硬编码单页字段."""
from __future__ import annotations

import re
from typing import Optional

_PLACEHOLDER_SEL_RE = re.compile(
    r'^placeholder:(?:"([^"]+)"|\'([^\']+)\')$',
    re.IGNORECASE,
)

# 范围日期控件常见占位符: 页面上常有多组, 不能单独作为稳定 selector
_AMBIGUOUS_RANGE_PLACEHOLDER_RES = (
    re.compile(r"开始|结束", re.IGNORECASE),
    re.compile(r"\b(start|end)\b", re.IGNORECASE),
    re.compile(r"\b(from|to)\b", re.IGNORECASE),
    re.compile(r"date", re.IGNORECASE),
    re.compile(r"时间", re.IGNORECASE),
    re.compile(r"请选择", re.IGNORECASE),
    re.compile(r"select", re.IGNORECASE),
    re.compile(r"pick", re.IGNORECASE),
)


def placeholder_name_from_selector(sel: str) -> Optional[str]:
    m = _PLACEHOLDER_SEL_RE.match((sel or "").strip())
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip()


def is_ambiguous_range_placeholder_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) <= 12:
        # 短占位符 (开始日期/End date 等) 在多字段页几乎都不唯一
        for pat in _AMBIGUOUS_RANGE_PLACEHOLDER_RES:
            if pat.search(n):
                return True
        return len(n) <= 8
    return False


def is_bare_range_placeholder_selector(sel: str) -> bool:
    name = placeholder_name_from_selector(sel)
    if name is None:
        return False
    return is_ambiguous_range_placeholder_name(name)


def extract_date_field_label(intent: str) -> str:
    """从 intent 提取日期字段名 (点击触发器 / 面板选日均可用)."""
    from .skill_dom_helpers import _extract_date_picker_field_from_intent

    field = _extract_date_picker_field_from_intent(intent or "")
    if field:
        return field
    m = re.search(
        r"在\s*[\"'「]?([^\"'」\s，。]{1,20})[\"'」]?\s*日期面板",
        intent or "",
    )
    if m:
        return m.group(1).strip()
    return ""


def is_weak_date_placeholder_for_intent(sel: str, intent: str) -> bool:
    """intent 已指明字段时, 裸范围 placeholder 不能回填/不能作为终态 selector."""
    if not is_bare_range_placeholder_selector(sel):
        return False
    return bool(extract_date_field_label(intent))


def is_weak_date_label_text_selector(sel: str, intent: str) -> bool:
    """text=\"字段名\" 点到 label, 非日期输入控件."""
    from .skill_resolver import extract_target_text_from_intent

    if not re.match(r'^text="[^"]+"$', (sel or "").strip()):
        return False
    field = extract_target_text_from_intent(intent) or extract_date_field_label(intent)
    if not field:
        return False
    return field in sel


def is_strong_date_picker_selector(sel: str) -> bool:
    s = (sel or "").strip()
    if not s or is_bare_range_placeholder_selector(s):
        return False
    if s.startswith("input#") or (s.startswith("#") and " " not in s):
        return True
    if "ant-form-item" in s and "label" in s:
        return True
    if s.startswith("xpath=") or s.startswith("(//") or s.startswith("//"):
        return "label" in s or "form-item" in s or "@id=" in s or "@for" in s
    return False
