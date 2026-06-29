"""变量替换工具 —— 将步骤/预期中的 ${varName} 替换为运行时值."""
from __future__ import annotations

import json
import re
from typing import Any

_API_CTX_SKIP_KEYS = frozenset({"ops", "_ops_index"})
_PLACEHOLDER_RE = re.compile(r"\$\{(\w+)\}")
# api_call 执行前写入 extras, 供 API 模板 ${var} 与步骤引用变量对齐 (如 orderId7 → orderId).
API_PLACEHOLDER_REFS_KEY = "_placeholder_refs"


def extract_placeholder_names(*texts: str | None) -> list[str]:
    """从文本中提取 ${varName} 占位符名 (去重, 保持顺序)."""
    seen: set[str] = set()
    names: list[str] = []
    for text in texts:
        if not text:
            continue
        for m in _PLACEHOLDER_RE.finditer(text):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def collect_placeholder_bindings(
    *texts: str | None,
    context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """收集文本中引用的 ${name} 在 context 中的已解析值."""
    ctx = context or {}
    out: dict[str, str] = {}
    for name in extract_placeholder_names(*texts):
        if name in ctx and ctx[name] is not None:
            out[name] = str(ctx[name])
    return out


def resolve_placeholder_alias(
    placeholder: str,
    refs: dict[str, str],
) -> str | None:
    """模板占位符与步骤引用变量对齐: 精确名或「基名+数字后缀」唯一匹配.

    例: 模板 ${orderId}, 步骤引用 orderId7 → 返回 orderId7 的值.
    """
    if not placeholder or not refs:
        return None
    if placeholder in refs:
        return refs[placeholder]
    matches = [
        v
        for k, v in refs.items()
        if k.startswith(placeholder)
        and (len(k) == len(placeholder) or k[len(placeholder) :].isdigit())
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _enum_maps_from_param_rules(api_tpl: Any) -> dict[str, dict[str, Any]]:
    """从 API 模板的 param_rules 构建 field → {中文标签: 枚举值}."""
    rules = getattr(api_tpl, "param_rules", []) or []
    out: dict[str, dict[str, Any]] = {}
    for rule in rules:
        field = str(rule.get("field") or "").strip()
        enum_map = rule.get("enum") or {}
        if field and isinstance(enum_map, dict) and enum_map:
            out[field] = enum_map
    return out


def _resolve_enum_label(field: str, value: Any, enum_maps: dict[str, dict[str, Any]]) -> Any:
    """将 param_rules 中的中文标签解析为枚举值; 已是数字或 ${var} 则原样返回."""
    if value is None:
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or "${" in text:
        return value
    field_map = enum_maps.get(field) or {}
    if text in field_map:
        return field_map[text]
    if text.isdigit():
        return int(text)
    return value


def normalize_api_flat_params(
    flat: dict[str, Any],
    api_tpl: Any,
) -> dict[str, Any]:
    """合并 intent / extras 后的平铺 API 参数: 枚举中文→数字, 去掉模板外字段.

    - deliver 等 param_rules API: extras 里 subject='数学' 会落成 subject=2
    - timeout 等标量传参: orderId='${orderId8}' 不含枚举, 原样保留
    - 规划误写的 grade 会映射到 period (若模板有 period 枚举)
    """
    if not flat:
        return {}
    enum_maps = _enum_maps_from_param_rules(api_tpl)
    allowed = set((getattr(api_tpl, "params", None) or {}).keys())
    allowed |= set((getattr(api_tpl, "body", None) or {}).keys())

    out: dict[str, Any] = {}
    for key, val in flat.items():
        if allowed and key not in allowed:
            if key == "grade" and "period" in allowed and "period" not in flat:
                out["period"] = _resolve_enum_label("period", val, enum_maps)
            continue
        out[key] = _resolve_enum_label(key, val, enum_maps)
    return out


def extract_explicit_api_params(line: str) -> dict[str, Any]:
    """从步骤文本解析显式 API 参数: 「传参 orderId=1, op=7」或「params: orderId=1」.

    返回平铺 dict, 由 ApiRunner 按模板归入 params/body.
    """
    if not line:
        return {}
    m = re.search(r"(?:传参|params[:：])\s*(.+)$", line.strip(), re.I)
    if not m:
        return {}
    segment = m.group(1).strip()
    out: dict[str, Any] = {}
    for part in re.split(r"[,，]\s*", segment):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"「」")
        if not key:
            continue
        if val.isdigit():
            out[key] = int(val)
        else:
            out[key] = val
    return out


def substitute_variables(text: str, context: dict[str, Any]) -> str:
    """将 ${varName} 替换为 context 中的值.

    例: "工单ID=${orderId1}的生产状态" + {"orderId1": "118743302"}
       → "工单ID=118743302的生产状态"
    """
    if not context:
        return text
    for k, v in context.items():
        # 只替换 ${name} 这种显式占位符, 避免误替换普通业务文本.
        placeholder = "${" + k + "}"
        if placeholder in text:
            text = text.replace(placeholder, str(v))
    return text


def find_api_var_for_value(text: str, context: dict[str, Any]) -> str | None:
    """若字面量等于 context 中某 API 标量值, 返回变量名 (优先 orderId/id 类)."""
    raw = (text or "").strip()
    if not raw or not context:
        return None
    matches: list[str] = []
    for k, v in context.items():
        if k in _API_CTX_SKIP_KEYS or isinstance(v, (dict, list)):
            continue
        if str(v) == raw:
            matches.append(k)
    if not matches:
        return None

    def _rank(key: str) -> tuple[int, str]:
        kl = key.lower()
        if "orderid" in kl or re.search(r"id\d+$", kl) or key.endswith("Id"):
            return (0, key)
        return (1, key)

    matches.sort(key=_rank)
    return matches[0]


def substitute_in_list(items: list[str], context: dict[str, Any]) -> list[str]:
    """批量替换列表中的字符串."""
    if not context:
        # 没有上下文时原样返回, 保持调用方列表对象不被无意义复制.
        return items
    return [substitute_variables(item, context) for item in items]


def format_session_context(
    ctx: dict[str, Any] | None,
    session_ops_cfg: dict[str, Any] | None = None,
) -> str:
    """将跨用例会话变量/ops 格式化为动作规划可读摘要."""
    if not ctx:
        return "(无)"
    cfg = session_ops_cfg or {}
    table_field = str(cfg.get("table_row_field") or "").strip() or "行主键"
    index_by = cfg.get("index_by") or []
    if isinstance(index_by, str):
        index_by = [index_by]

    lines: list[str] = []
    skip = frozenset({"ops", "_ops_index"})
    scalars: list[str] = []
    for k, v in sorted(ctx.items()):
        if k in skip or isinstance(v, (dict, list)):
            continue
        scalars.append(f"- {k} = {v}")
    if scalars:
        lines.append("标量变量 (步骤中可用 ${名称} 引用):")
        lines.extend(scalars)

    ops = ctx.get("ops")
    if isinstance(ops, dict) and ops:
        lines.append("ops 记录 (可选 bind_session; 一般用 api_call 标量变量即可):")
        for eid, entry in ops.items():
            if not isinstance(entry, dict):
                continue
            row_val = entry.get(table_field) or entry.get("orderId") or ""
            if index_by and row_val:
                tags = [
                    f"{f}={entry.get(f)!r}"
                    for f in index_by
                    if entry.get(f) not in (None, "")
                ]
                if tags:
                    lines.append(f"- {' | '.join(tags)} → {table_field}={row_val}")
                    continue
            lines.append(
                f"- ops[{eid}] = {json.dumps(entry, ensure_ascii=False)}"
            )
    idx = ctx.get("_ops_index")
    if isinstance(idx, dict) and idx:
        lines.append("ops 反向索引 (索引字段值 → 实体ID):")
        for field, bucket in idx.items():
            if not isinstance(bucket, dict) or not bucket:
                continue
            pairs = ", ".join(
                f"{k!r}→{v}" for k, v in list(bucket.items())[:12]
            )
            lines.append(f"- {field}: {pairs}")

    return "\n".join(lines) if lines else "(无)"
