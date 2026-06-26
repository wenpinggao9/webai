"""日期控件适配器链: Ant / Element / 通用日历.

面板选日优先「月份表头 + 日格」xpath, 不依赖单一组件库 class.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from .intent_route import is_date_panel_end_side, is_date_panel_start_side

SemanticNode = Dict[str, Any]
DatePickerKind = Literal["ant", "element", "generic"]

_EN_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_ANT_DOM_HINTS = ("ant-picker", "ant-picker-dropdown", "ant-picker-cell", "ant-picker-panel")
_ELEMENT_DOM_HINTS = ("el-date-table", "el-picker-panel", "el-date-picker", "el-date-editor")
_DATE_PANEL_CLASS_HINTS = (
    "ant-picker-dropdown", "ant-picker-body", "ant-picker-content",
    "ant-picker-panel", "ant-picker-cell", "ant-picker-cell-inner",
    "el-date-table", "el-picker-panel", "el-date-picker",
    "rc-picker-dropdown", "rc-picker-panel", "mx-datepicker", "datepicker-popup",
)


def _escape_xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{p}"' for p in parts) + ")"


def parse_iso_date_parts(date_val: str) -> Optional[tuple[int, int, int]]:
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", (date_val or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def month_markers_for_parts(year: int, month: int) -> List[str]:
    markers = [
        f"{year}年{month}月",
        f"{year}-{month:02d}",
        f"{year}/{month:02d}",
    ]
    if 1 <= month <= 12:
        markers.append(f"{year}年{_EN_MONTH_ABBR[month - 1]}")
        markers.append(_EN_MONTH_ABBR[month - 1])
    return markers


def xpath_day_in_month_table(year: int, month: int, day: int) -> str:
    """跨组件库: 按月份表头锁定 table, 再点目标日格."""
    day_lit = _escape_xpath_literal(str(day))
    hdr = " or ".join(
        f"contains(normalize-space(.), {_escape_xpath_literal(m)})"
        for m in month_markers_for_parts(year, month)
    )
    return (
        f"(//*[self::th or self::td or self::div or self::span][{hdr}]/ancestor::table[1]"
        f"//td[(normalize-space(.)={day_lit} or .//div[normalize-space(.)={day_lit}]"
        f" or .//span[normalize-space(.)={day_lit}])"
        f" and not(contains(@class,'disabled')) and not(contains(@class,'off'))])[1]"
    )


def detect_date_picker_kind(semantic_dom: List[SemanticNode]) -> DatePickerKind:
    for node in semantic_dom:
        cls = str(node.get("class") or "").lower()
        if any(h in cls for h in _ANT_DOM_HINTS):
            return "ant"
    for node in semantic_dom:
        cls = str(node.get("class") or "").lower()
        if any(h in cls for h in _ELEMENT_DOM_HINTS):
            return "element"
    return "generic"


def detect_date_panel_open(semantic_dom: List[SemanticNode]) -> bool:
    day_cell_count = 0
    has_month_header = False
    for node in semantic_dom:
        cls_blob = str(node.get("class") or "").lower()
        if any(hint in cls_blob for hint in _DATE_PANEL_CLASS_HINTS):
            return True
        text = (node.get("text") or "").strip()
        if re.search(r"\d{4}\s*年", text) or re.search(r"\d{4}[-/]\d{1,2}", text):
            has_month_header = True
        if any(mon in text for mon in _EN_MONTH_ABBR):
            has_month_header = True
        tag = (str(node.get("tag") or "")).lower()
        if tag == "td" and re.fullmatch(r"\d{1,2}", text):
            if 1 <= int(text) <= 31:
                day_cell_count += 1
    return day_cell_count >= 14 or (day_cell_count >= 7 and has_month_header)


def _dedupe(candidates: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for s in candidates:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _calendar_bounds_for_month(
    semantic_dom: List[SemanticNode],
    header_indices: List[int],
    year: int,
    month: int,
) -> tuple[int, int]:
    markers = month_markers_for_parts(year, month)
    matched = []
    for idx in header_indices:
        node = semantic_dom[idx]
        blob = f"{node.get('text') or ''} {node.get('class') or ''}"
        if any(m in blob for m in markers):
            matched.append(idx)
    if not matched:
        start = header_indices[0] if header_indices else 0
        end = header_indices[1] if len(header_indices) > 1 else len(semantic_dom)
        return start, end
    start = matched[0]
    end = len(semantic_dom)
    for idx in header_indices:
        if idx > start:
            end = idx
            break
    return start, end


def _semantic_calendar_selectors(
    semantic_dom: List[SemanticNode],
    date_val: str,
) -> List[str]:
    parts = parse_iso_date_parts(date_val)
    if not parts:
        return []
    year, month, day = parts
    day_str = str(day)
    day_lit = _escape_xpath_literal(day_str)
    month_markers = month_markers_for_parts(year, month)

    header_indices: List[int] = []
    for i, node in enumerate(semantic_dom):
        blob = f"{node.get('text') or ''} {node.get('class') or ''}"
        if any(m in blob for m in month_markers):
            header_indices.append(i)

    start, end = _calendar_bounds_for_month(semantic_dom, header_indices, year, month)
    selectors: List[str] = [xpath_day_in_month_table(year, month, day)]
    selectors.append(
        f"(//div[contains(@class,'picker') or contains(@class,'calendar') or contains(@class,'date')]"
        f"//td[normalize-space(.)={day_lit} or .//div[normalize-space(.)={day_lit}]])[1]"
    )

    hits: List[tuple[int, int, SemanticNode]] = []
    for i in range(start, end):
        node = semantic_dom[i]
        tag = (str(node.get("tag") or "")).lower()
        text = (str(node.get("text") or "")).strip()
        if tag not in ("td", "div", "span") or text != day_str:
            continue
        cls = str(node.get("class") or "").lower()
        if "disabled" in cls or "off" in cls:
            continue
        tag_rank = 0 if tag == "td" else (1 if tag == "div" else 2)
        hits.append((tag_rank, i, node))

    hits.sort(key=lambda x: (x[0], x[1]))
    for _, _, node in hits[:3]:
        el_id = str(node.get("id") or "").strip()
        if el_id:
            selectors.append(f"#{el_id}")
        tag = (str(node.get("tag") or "")).lower()
        if tag == "td":
            selectors.append(f'td:has(div:text-is("{day_str}"))')
        elif tag == "div":
            selectors.append(f'div:text-is("{day_str}")')
    return selectors


def build_panel_date_candidates(
    semantic_dom: List[SemanticNode],
    date_val: str,
    intent: str,
    kind: DatePickerKind,
) -> List[str]:
    parts = parse_iso_date_parts(date_val)
    if not parts:
        return []
    year, month, day = parts
    date_lit = _escape_xpath_literal(date_val)
    day_lit = _escape_xpath_literal(str(day))
    candidates: List[str] = [xpath_day_in_month_table(year, month, day)]

    candidates.extend([
        f"(//td[contains(@title, {date_lit})])[1]",
        f"(//td[@data-date={date_lit}])[1]",
    ])

    if kind == "ant":
        panel = "(//div[contains(@class,'ant-picker-panel')])"
        if is_date_panel_end_side(intent):
            panel = "(//div[contains(@class,'ant-picker-panel')])[2]"
        elif is_date_panel_start_side(intent):
            panel = "(//div[contains(@class,'ant-picker-panel')])[1]"
        candidates.extend([
            f"({panel}//td[contains(@title, {date_lit})])[1]",
            f"({panel}//td[normalize-space(.)={day_lit} or .//div[normalize-space(.)={day_lit}]])[1]",
            f"(//div[contains(@class,'ant-picker-dropdown')]//td[contains(@title, {date_lit})])[1]",
            f"(//td[contains(@title, {date_lit}) and contains(@class,'ant-picker-cell-in-view')])[1]",
        ])
        if is_date_panel_start_side(intent):
            candidates.append(f'.ant-picker-panel:first-child td:has(div:text-is("{day}"))')
        elif is_date_panel_end_side(intent):
            candidates.append(f'.ant-picker-panel:nth-child(2) td:has(div:text-is("{day}"))')

    if kind == "element":
        candidates.extend([
            f"(//div[contains(@class,'el-picker-panel')]//td[contains(@class,'available')]"
            f"//span[normalize-space(.)={day_lit}])[1]",
            f"(//div[contains(@class,'el-date-table')]//td[.//span[normalize-space(.)={day_lit}]])[1]",
        ])

    candidates.extend(_semantic_calendar_selectors(semantic_dom, date_val))
    return _dedupe(candidates)


def build_trigger_date_candidates(
    semantic_dom: List[SemanticNode],
    field: str,
    kind: DatePickerKind,
) -> List[str]:
    te = _escape_xpath_literal(field.strip())
    scoped: List[str] = []
    bare: List[str] = []

    for i, node in enumerate(semantic_dom):
        tag = (str(node.get("tag") or "")).lower()
        text = (str(node.get("text") or "")).strip()
        if tag == "label" and field in text:
            for near in semantic_dom[i + 1 : i + 5]:
                if (str(near.get("tag") or "")).lower() != "input":
                    continue
                el_id = str(near.get("id") or "").strip()
                if el_id:
                    scoped.insert(0, f"input#{el_id}")
                    scoped.insert(1, f"#{el_id}")
                break

    scoped.extend([
        f"(//input[@id=(//label[contains(normalize-space(.), {te})]/@for)][1]",
        f"(//label[contains(normalize-space(.), {te})]/ancestor::div[contains(@class,'ant-form-item')]//input)[1]",
        f"(//label[contains(normalize-space(.), {te})]/following-sibling::*//input)[1]",
        f"(//input[contains(@placeholder, {te}) and ancestor::div[contains(@class,'picker') or contains(@class,'date')]])[1]",
    ])

    if kind == "ant":
        scoped.extend([
            f"(//div[contains(@class,'ant-form-item')][.//label[contains(normalize-space(.), {te})]]"
            f"//input[contains(@class,'ant-picker-input')])[1]",
            f"(//div[contains(@class,'ant-form-item')][.//label[contains(normalize-space(.), {te})]]"
            f"//div[contains(@class,'ant-picker')])[1]",
        ])
    else:
        scoped.append("(//input[@type='date'])[1]")

    for ph in ("开始日期", "结束日期", "请选择日期", "Start date", "End date", field.strip()):
        if not ph:
            continue
        ph_lit = _escape_xpath_literal(ph)
        bare.append(f"(//input[contains(@placeholder, {ph_lit})])[1]")

    return _dedupe(scoped + bare)


def build_date_picker_candidates(
    semantic_dom: List[SemanticNode],
    intent: str,
    *,
    extract_field_fn: Any = None,
    extract_date_fn: Any = None,
    is_panel_intent_fn: Any = None,
) -> Dict[str, Any]:
    """统一入口: 根据 intent 场景返回 selector 候选."""
    if extract_field_fn is None or extract_date_fn is None or is_panel_intent_fn is None:
        from . import skill_dom_helpers as _h

        extract_field_fn = _h._extract_date_picker_field_from_intent
        extract_date_fn = _h._extract_date_value_from_intent
        is_panel_intent_fn = _h._intent_is_panel_date_selection

    field = extract_field_fn(intent or "")
    date_val = extract_date_fn(intent or "")
    kind = detect_date_picker_kind(semantic_dom)
    panel_open = detect_date_panel_open(semantic_dom)
    panel_mode = panel_open or (bool(date_val) and is_panel_intent_fn(intent or ""))

    candidates: List[str] = []
    if panel_mode:
        if date_val:
            candidates.extend(build_panel_date_candidates(semantic_dom, date_val, intent or "", kind))
        elif panel_open:
            candidates.extend([
                "(//td[contains(@class,'ant-picker-cell-in-view') and not(contains(@class,'ant-picker-cell-disabled'))])[1]",
                "(//div[contains(@class,'el-date-table')]//td[contains(@class,'available')])[1]",
            ])
    else:
        if not field:
            return {"selector": None, "candidates": [], "field_label": "", "kind": kind}
        candidates = build_trigger_date_candidates(semantic_dom, field, kind)

    deduped = _dedupe(candidates)
    return {
        "selector": deduped[0] if deduped else None,
        "candidates": deduped,
        "field_label": field or "",
        "kind": kind,
    }
