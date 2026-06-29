"""API 客户端 —— 按 Profile 中定义的模板执行 HTTP 请求.

职责:
  - 替换模板中的 ${var} 占位符 (body/params/url)
  - 从 DB 查询分配 TID 填入 ${tid}
  - 发 HTTP 请求 (GET/POST)
  - 提取 returns 字段存入上下文
"""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin

import requests

from ...foundation.profile import ApiTemplate, SystemProfile
from ...foundation.variable_substitution import resolve_placeholder_alias


class APIClient:
    """按 SystemProfile 中的 API 模板发起请求并提取返回变量."""

    def __init__(self, profile: SystemProfile) -> None:
        self.profile = profile

    def call(
        self,
        api_name: str,
        params: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        *,
        var_refs: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """调用指定 API."""
        tpl = self.profile.apis.get(api_name)
        if not tpl:
            raise ValueError(f"API '{api_name}' 未在 profile 中定义. 可用: {list(self.profile.apis.keys())}")

        if getattr(tpl, "type", None) == "db":
            return self._query_db(tpl, params or {}, context or {})

        data = self._build_params(tpl, params or {}, context or {}, var_refs=var_refs or {})
        self._ensure_params_resolved(data)

        url = self._resolve_url(api_name, tpl, data)
        if tpl.method == "POST":
            resp = requests.post(url, json=data.get("body"), params=data.get("params"), timeout=30)
        else:
            resp = requests.get(url, params=data.get("params"), timeout=30)

        resp.raise_for_status()
        text = (resp.text or "").strip()
        if not text:
            raise ValueError(
                f"API {api_name} 响应为空: status={resp.status_code}, url={url}"
            )
        try:
            result = resp.json()
        except ValueError as e:
            raise ValueError(
                f"API {api_name} 响应非 JSON: status={resp.status_code}, url={url}, "
                f"params={data.get('params')!r}, body={data.get('body')!r}, "
                f"body_preview={text[:300]!r}"
            ) from e

        return result

    def preview_request(
        self,
        api_name: str,
        params: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        *,
        var_refs: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """构建即将发出的请求 (不实际调用), 供日志打印."""
        tpl = self.profile.apis.get(api_name)
        if not tpl:
            return {"api_name": api_name, "error": f"未定义, 可用: {list(self.profile.apis.keys())}"}
        if getattr(tpl, "type", None) == "db":
            return {"api_name": api_name, "type": "db", "query": getattr(tpl, "query", "(profile.database.query)")}

        data = self._build_params(tpl, params or {}, context or {}, var_refs=var_refs or {})
        url = self._resolve_url(api_name, tpl, data)
        return {
            "api_name": api_name,
            "method": tpl.method,
            "url": url,
            "params": data.get("params"),
            "body": data.get("body"),
        }

    def _resolve_url(self, api_name: str, tpl: ApiTemplate, data: dict) -> str:
        """拼接最终请求 URL: 完整 url 直用; 否则 base + 相对路径."""
        raw = (tpl.url or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        api_base = (tpl.base_url or self.profile.api_base_url or self.profile.base_url or "").rstrip("/")
        if not api_base:
            raise ValueError(
                f"API {api_name} 无可用域名: 请在业务知识配置 api_base_url 或该 API 的 base_url"
            )
        return urljoin(api_base + "/", raw.lstrip("/"))

    def _query_db(self, tpl: ApiTemplate, params: dict, context: dict) -> dict[str, Any]:
        """执行 DB 查询, 返回结果列表."""
        import pymysql
        db = self.profile.database
        query_tpl = db.get("query", "")
        table_prefix = db.get("table_prefix", "tblHomework")
        shard_count = db.get("shard_count", 1)
        limit = db.get("limit", 10)

        all_tids = []
        for i in range(shard_count):
            table = f"{table_prefix}{i}"
            query = query_tpl.format(table=table, limit=limit)
            query = _substitute(query, context)

            conn = pymysql.connect(
                host=db["host"], port=db["port"], user=db["user"],
                password=db["password"], database=db["db"],
                charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                all_tids.extend(str(r["tid"]) for r in rows if "tid" in r)
            finally:
                conn.close()

        return {"tids": all_tids}

    def allocate_tid(self) -> int:
        """从 DB 查询可用 TID, 取第一个."""
        result = self._query_db(type('T', (), {'type': 'db'})(), {}, {})
        tids = result.get("tids", [])
        if not tids:
            raise ValueError("DB 查询无可用 TID")
        return int(tids[0])

    def resolve_enum(self, enum_name: str, key: str) -> Optional[int]:
        """查枚举值, 如 profile.enums.period["大学"] → 80."""
        enum_map = self.profile.enums.get(enum_name, {})
        if key in enum_map:
            return enum_map[key]
        try:
            return int(key)
        except ValueError:
            return None

    def _build_params(
        self,
        tpl: ApiTemplate,
        extra: dict,
        context: dict,
        *,
        var_refs: dict[str, str],
    ) -> dict:
        """合并模板参数与调用参数, 并递归替换变量占位符."""
        data: dict[str, Any] = {}
        if "body" in extra or "params" in extra:
            body_extra = extra.get("body", {})
            params_extra = extra.get("params", {})
        else:
            body_extra = dict(extra)
            params_extra = {}

        for part_name, extra_src in [("params", params_extra), ("body", body_extra)]:
            src = getattr(tpl, part_name)
            if not src:
                continue
            merged = dict(src)
            merged.update(extra_src)
            sub_ctx = {**(context or {}), **extra_src, **var_refs}
            merged = substitute_with_refs(merged, sub_ctx, var_refs)
            data[part_name] = merged
        return data

    @staticmethod
    def _ensure_params_resolved(data: dict) -> None:
        for part in ("params", "body"):
            blob = data.get(part)
            if blob is not None and has_unresolved_placeholder(blob):
                raise ValueError(f"API 参数含未替换占位符: {part}={blob!r}")

    def _extract_returns(self, tpl: ApiTemplate, result: dict) -> dict[str, Any]:
        """按 returns 配置从响应 JSON 中提取变量."""
        extracted = {}
        for ret_name in tpl.returns:
            value = _get_nested(result, ret_name)
            if value is not None:
                extracted[ret_name.split(".")[-1]] = str(value)
            else:
                extracted[ret_name.split(".")[-1]] = None
        return extracted


def has_unresolved_placeholder(obj: Any) -> bool:
    if isinstance(obj, str):
        return "${" in obj
    if isinstance(obj, dict):
        return any(has_unresolved_placeholder(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_unresolved_placeholder(v) for v in obj)
    return False


def substitute_with_refs(
    obj: Any,
    context: dict[str, Any],
    var_refs: dict[str, str],
) -> Any:
    """先按 context 精确替换 ${name}, 再按步骤引用 var_refs 做基名别名解析."""
    resolved = _substitute(obj, context)
    return _apply_ref_aliases(resolved, var_refs)


def _apply_ref_aliases(obj: Any, refs: dict[str, str]) -> Any:
    if isinstance(obj, str):
        out = obj
        for token in list(_unresolved_placeholders(obj)):
            val = resolve_placeholder_alias(token, refs)
            if val is not None:
                out = out.replace(f"${{{token}}}", val)
        return out
    if isinstance(obj, dict):
        return {k: _apply_ref_aliases(v, refs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_ref_aliases(v, refs) for v in obj]
    return obj


def _unresolved_placeholders(text: str) -> list[str]:
    import re
    seen: set[str] = set()
    names: list[str] = []
    for m in re.finditer(r"\$\{(\w+)\}", text):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _substitute(obj: Any, context: dict) -> Any:
    """递归替换 dict/list/str 中的 ${var}."""
    if isinstance(obj, str):
        for k, v in context.items():
            obj = obj.replace(f"${{{k}}}", str(v))
        return obj
    if isinstance(obj, dict):
        return {k: _substitute(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(v, context) for v in obj]
    return obj


def _get_nested(data: dict, path: str) -> Any:
    """按点路径取嵌套值: "data.orderId" → data["data"]["orderId"]."""
    parts = path.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur
