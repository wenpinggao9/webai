"""步骤⑨ 第2级 选择器记忆库 (L2).

持久化到文件, 跨批次复用. 成功 +1 / 失败 -1, 降到 0 删除.
向 V3 看齐: node_signature 节点签名、component_library 框架识别、
page_entries/generic_entries 双存储、压缩淘汰 stale 条目.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from .normalize import (
    normalize_intent,
    normalize_intent_legacy,
    normalize_url,
    normalize_url_legacy,
)
from .accel_paths import (
    L2_GENERIC_FILE,
    SELECTOR_MEMORY_FILE,
    l2_generic_path,
    l2_pages_dir,
    l2_route_path,
    migrate_l2_monolith_to_routes,
    resolve_accel_dir_from_memory_arg,
    selector_memory_path,
)
from .playwright_api import normalize_info
_COMPRESS_STALE_SECONDS = 14 * 24 * 3600  # 14 天
_FILE_VERSION = 1


def _build_node_signature(node: Optional[dict]) -> dict[str, str]:
    """从 semantic_dom 节点提取特征签名, 用于失效检测."""
    if not node:
        return {}
    tag = str(node.get("tag") or "").lower()
    text = str(node.get("text") or "").strip()[:80]
    raw_class = str(node.get("class") or "")
    class_parts = [
        c for c in raw_class.split()
        if c and not c.startswith("_") and len(c) > 1
    ]
    class_pattern = " ".join(class_parts[:2]) if class_parts else ""
    role = str(node.get("role") or "").strip()
    return {
        "tag": tag,
        "text": text,
        "role": role,
        "class_pattern": class_pattern,
    }


def _instantiate_generic_template(template: str, target_text: str) -> str:
    if not template:
        return ""
    text = (target_text or "").strip()
    if not text:
        return template
    for ph in ("{text}", "{label}", "{{text}}", "{{label}}"):
        if ph in template:
            return template.replace(ph, text)
    if ":has-text" not in template:
        return f'{template}:has-text("{text}")'
    return template


def _detect_component_library(items: list[dict]) -> str:
    """扫描 DOM 的 class 前缀识别组件库."""
    prefix_counts: dict[str, int] = {}
    for it in items:
        raw = str(it.get("class") or "")
        for cls in raw.split():
            if "-" in cls and len(cls) >= 3:
                prefix = cls.split("-")[0].lower()
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    if not prefix_counts:
        return "generic"
    top = max(prefix_counts, key=prefix_counts.get)
    mapping = {
        "el": "element-ui", "elx": "element-plus", "ant": "ant-design",
        "van": "vant", "ivu": "iview", "iv": "iview",
        "mui": "material-ui", "chakra": "chakra-ui",
        "nb": "ng-bootstrap", "mat": "angular-material", "p": "prime-ng",
    }
    return mapping.get(top, "generic")


class SelectorMemory:
    """中期记忆库: L2_pages 按 route 分文件 + _generic.json."""

    def __init__(self, path_or_accel: str | Path, ttl_s: int = 0) -> None:
        del ttl_s
        self._accel_dir = resolve_accel_dir_from_memory_arg(path_or_accel)
        self.path = l2_pages_dir(self._accel_dir)  # 兼容属性
        self._store: dict[str, dict] = {}
        self._generic_store: dict[str, dict] = {}
        self._loaded_routes: set[str] = set()
        self._dirty_routes: set[str] = set()
        self._stats_lookups = 0
        self._stats_hits = 0
        self._stats_generic_lookups = 0
        self._stats_generic_hits = 0
        self._load_all()
        self._compress()

    def _full_key(self, url: str, action_type: str, intent: str) -> str:
        return self._key(url, action_type, intent)

    def _route_of_key(self, full_key: str) -> str:
        return str(full_key).split("|", 1)[0]

    def _ensure_route_loaded(self, url: str) -> str:
        route = normalize_url(url)
        if route in self._loaded_routes:
            return route
        self._load_route_file(route)
        self._loaded_routes.add(route)
        return route

    def _load_route_file(self, route: str) -> None:
        fp = l2_route_path(self._accel_dir, route)
        if not fp.is_file():
            return
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            entries = data.get("entries") or {}
            for short_key, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                if entry.get("success_count", 0) <= 0:
                    continue
                self._store[f"{route}|{short_key}"] = entry
        except Exception:
            pass

    def _load_all(self) -> None:
        migrate_l2_monolith_to_routes(self._accel_dir)
        pages = l2_pages_dir(self._accel_dir)
        if not pages.is_dir():
            return
        for fp in pages.glob("*.json"):
            if fp.name in (SELECTOR_MEMORY_FILE, L2_GENERIC_FILE):
                continue
            if fp.name.endswith(".bak"):
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            route = data.get("route")
            if not route:
                stem = fp.stem.replace("__", "/")
                route = "/" + stem if stem != "root" else "/"
            self._loaded_routes.add(route)
            for short_key, entry in (data.get("entries") or {}).items():
                if isinstance(entry, dict) and entry.get("success_count", 0) > 0:
                    self._store[f"{route}|{short_key}"] = entry
        self._load_generic()

    def _load_generic(self) -> None:
        gp = l2_generic_path(self._accel_dir)
        if not gp.is_file():
            monolith = selector_memory_path(self._accel_dir)
            if monolith.is_file():
                try:
                    data = json.loads(monolith.read_text(encoding="utf-8"))
                    for k, v in (data.get("generic_entries") or {}).items():
                        if v.get("success_count", 0) > 0:
                            self._generic_store[k] = v
                except Exception:
                    pass
            return
        try:
            data = json.loads(gp.read_text(encoding="utf-8"))
            for k, v in (data.get("generic_entries") or {}).items():
                if isinstance(v, dict) and v.get("success_count", 0) > 0:
                    self._generic_store[k] = v
        except Exception:
            pass

    def _mark_dirty(self, url: str) -> None:
        self._dirty_routes.add(normalize_url(url))

    def _key(self, url: str, action_type: str, intent: str) -> str:
        return f"{normalize_url(url)}|{action_type}|{normalize_intent(intent)}"

    def _legacy_key(self, url: str, action_type: str, intent: str) -> str:
        return (
            f"{normalize_url_legacy(url)}|{action_type}|"
            f"{normalize_intent_legacy(intent)}"
        )

    def _keys_for_lookup(self, url: str, action_type: str, intent: str) -> list[str]:
        primary = self._key(url, action_type, intent)
        legacy = self._legacy_key(url, action_type, intent)
        if legacy == primary:
            return [primary]
        return [primary, legacy]

    def _get_entry(self, url: str, action_type: str, intent: str) -> Optional[dict]:
        self._ensure_route_loaded(url)
        for k in self._keys_for_lookup(url, action_type, intent):
            e = self._store.get(k)
            if e and e.get("success_count", 0) > 0:
                return e
        return None

    def _resolve_store_key(self, url: str, action_type: str, intent: str) -> Optional[str]:
        for k in self._keys_for_lookup(url, action_type, intent):
            e = self._store.get(k)
            if e and e.get("success_count", 0) > 0:
                return k
        return None

    def _migrate_to_canonical(self, url: str, action_type: str, intent: str) -> str:
        canon = self._key(url, action_type, intent)
        found = self._resolve_store_key(url, action_type, intent)
        if found and found != canon:
            self._store[canon] = self._store[found]
            for alt in self._keys_for_lookup(url, action_type, intent):
                if alt != canon:
                    self._store.pop(alt, None)
        return canon

    # ── 页面级查找 ─────────────────────────────────────────────

    def get(self, url: str, action_type: str, intent: str) -> Optional[dict]:
        """页面级查找. 返回规范化 info dict."""
        e = self._get_entry(url, action_type, intent)
        if not e:
            return None
        return normalize_info(e)

    def lookup_validate(
        self,
        page: Any,
        url: str,
        action_type: str,
        intent: str,
    ) -> Optional[dict]:
        """原子操作: 查找 + 验证 + 加分.

        命中 → 验证 selector 在当前页面是否匹配可见元素:
          - 有效: success_count +1, 返回 info
          - 无效: success_count -1, 返回 None (降到 0 自动删除)
        """
        info = self.get(url, action_type, intent)
        if info is None:
            return None

        self._stats_lookups += 1
        selector = info.get("selector", "")
        if not selector or not page:
            self._decrement(url, action_type, intent)
            return None

        if self._validate_locator_info(page, info):
            k = self._migrate_to_canonical(url, action_type, intent)
            e = self._store.get(k)
            if not e:
                return None
            e["success_count"] = min(e.get("success_count", 1) + 1, 100)
            e["updated_at"] = time.time()
            self._stats_hits += 1
            return normalize_info(e)
        else:
            # 验证失败 → 减分
            self._decrement(url, action_type, intent)
            return None

    # ── 页面级写入 ─────────────────────────────────────────────

    def record_success(
        self,
        url: str,
        action_type: str,
        intent: str,
        info: dict,
        *,
        node: Optional[dict] = None,
        component_library: str = "unknown",
        selector_type: str = "css",
    ) -> None:
        """写入或更新页面级条目 (兼容旧 API).

        如果 key 已存在且 selector 相同 → 不重复加分 (lookup 已加过).
        如果 key 已存在但 selector 不同 → 覆盖并重置 score=1.
        如果是新 key → 创建条目 score=1.
        """
        k = self._migrate_to_canonical(url, action_type, intent)
        for alt in self._keys_for_lookup(url, action_type, intent):
            if alt != k:
                self._store.pop(alt, None)
        spec = normalize_info(info)
        now = time.time()
        selector = spec.get("selector", "")
        e = self._store.get(k)

        if e and e.get("selector") == selector:
            e["updated_at"] = now
            if selector_type and selector_type != "css":
                e["selector_type"] = selector_type
        else:
            sig = _build_node_signature(node)
            self._store[k] = {
                **spec,
                "success_count": 1,
                "created_at": now,
                "updated_at": now,
                "component_library": component_library,
                "selector_type": selector_type,
                "node_signature": sig,
            }
        self._mark_dirty(url)

    def record_failure(
        self,
        url: str,
        action_type: str,
        intent: str,
        selector: Optional[str] = None,
    ) -> None:
        """success_count -1; 降到 0 则删除条目."""
        k = self._resolve_store_key(url, action_type, intent)
        if not k:
            return
        e = self._store.get(k)
        if not e:
            return
        if selector and e.get("selector") != selector:
            return
        self._decrement(url, action_type, intent)

    # ── 组件级写入 ─────────────────────────────────────────────

    def put_generic(
        self,
        component_library: str,
        component_type: str,
        selector_template: str,
        selector_type: str = "css",
    ) -> None:
        """写入组件级通用模式 (如 ant-design 的 radio wrapper)."""
        if not selector_template or not component_library or not component_type:
            return
        k = f"{component_library}|{component_type}"
        entry = self._generic_store.get(k)
        now = time.time()
        if entry and entry.get("selector_template") == selector_template:
            entry["success_count"] = entry.get("success_count", 0) + 1
            entry["updated_at"] = now
        else:
            self._generic_store[k] = {
                "selector_template": selector_template,
                "selector_type": selector_type,
                "component_library": component_library,
                "component_type": component_type,
                "success_count": 1,
                "created_at": now,
                "updated_at": now,
            }

    def get_generic(
        self,
        component_library: str,
        component_type: str,
    ) -> Optional[dict]:
        """查找组件级通用模式."""
        k = f"{component_library}|{component_type}"
        return self._generic_store.get(k)

    def lookup_generic(
        self,
        page: Any,
        action_type: str,
        intent: str,
        semantic_items: Optional[list[dict]] = None,
        *,
        component_library: str = "unknown",
    ) -> Optional[dict]:
        """L2 组件级通用模式: 按组件库+类型实例化模板并校验."""
        from .skill_resolver import (
            extract_target_text_from_intent,
            info_from_recommended_selector,
            resolve_component_type,
        )

        items = semantic_items or []
        comp_type = resolve_component_type(items, intent, action_type)
        if not comp_type:
            return None
        # 日期控件由 L3 build_date_picker_selector 按字段名定位; 通用 text/placeholder 易误点 label
        if comp_type == "date_picker":
            return None

        self._stats_generic_lookups += 1
        lib = component_library
        if lib in ("unknown", "generic") and items:
            lib = _detect_component_library(items)
        target = extract_target_text_from_intent(intent) or ""
        if not target:
            return None

        for try_lib in (lib, "generic"):
            if try_lib in ("unknown", ""):
                continue
            entry = self.get_generic(try_lib, comp_type)
            if not entry:
                continue
            template = str(entry.get("selector_template") or "")
            selector = _instantiate_generic_template(template, target)
            if not selector:
                continue
            info = info_from_recommended_selector(selector)
            if self._validate_locator_info(page, info):
                self._stats_generic_hits += 1
                info["component_library"] = try_lib
                info["component_type"] = comp_type
                return normalize_info(info)
        return None

    def maybe_record_generic(
        self,
        intent: str,
        action_type: str,
        info: dict,
        *,
        semantic_items: Optional[list[dict]] = None,
        component_library: str = "unknown",
    ) -> None:
        """成功回填时, 若 selector 含目标文本则写入 generic 模板."""
        from .skill_resolver import extract_target_text_from_intent, resolve_component_type

        items = semantic_items or []
        comp_type = resolve_component_type(items, intent, action_type)
        if not comp_type:
            return
        lib = component_library
        if lib in ("unknown", "generic") and items:
            lib = _detect_component_library(items)
        if lib in ("unknown", "generic"):
            return
        target = extract_target_text_from_intent(intent) or ""
        sel = str(info.get("selector") or "")
        if not target or target not in sel:
            return
        template = sel.replace(target, "{text}")
        sel_type = "xpath" if sel.startswith(("/", "xpath=")) else "css"
        self.put_generic(lib, comp_type, template, selector_type=sel_type)

    @property
    def stats(self) -> dict[str, Any]:
        lookups = self._stats_lookups or 1
        gen_lookups = self._stats_generic_lookups or 1
        return {
            "lookups": self._stats_lookups,
            "hits": self._stats_hits,
            "hit_rate": round(self._stats_hits / lookups * 100, 1),
            "generic_lookups": self._stats_generic_lookups,
            "generic_hits": self._stats_generic_hits,
            "generic_hit_rate": round(
                self._stats_generic_hits / gen_lookups * 100, 1,
            ),
            "page_entries": len(self._store),
            "generic_entries": len(self._generic_store),
        }

    # ── 内部方法 ───────────────────────────────────────────────

    def _decrement(self, url: str, action_type: str, intent: str) -> None:
        """success_count -1, 降到 0 删除."""
        k = self._resolve_store_key(url, action_type, intent)
        if not k:
            return
        e = self._store.get(k)
        if not e:
            return
        e["success_count"] = e.get("success_count", 1) - 1
        e["updated_at"] = time.time()
        if e["success_count"] <= 0:
            self._store.pop(k, None)
            self._mark_dirty(url)

    @staticmethod
    def _validate_locator_info(page: Any, info: dict) -> bool:
        """验证定位 info 在当前页面是否匹配到至少 1 个可见元素."""
        from .normalize import validate_selector

        if not page or not info:
            return False
        return validate_selector(page, normalize_info(info))

    @staticmethod
    def _validate_selector(page: Any, selector: str) -> bool:
        """兼容旧调用: 从 selector 字符串推断 method 后校验."""
        if not page or not selector:
            return False
        return SelectorMemory._validate_locator_info(
            page, normalize_info({"selector": selector}),
        )

    def _compress(self) -> None:
        """删除 success_count <= 1 且 created_at 超过 14 天的条目."""
        now = time.time()
        stale_threshold = now - _COMPRESS_STALE_SECONDS

        stale_keys = [
            k for k, v in self._store.items()
            if v.get("success_count", 0) <= 1
            and v.get("created_at", 0) < stale_threshold
        ]
        for k in stale_keys:
            del self._store[k]

        stale_generic = [
            k for k, v in self._generic_store.items()
            if v.get("success_count", 0) <= 1
            and v.get("created_at", 0) < stale_threshold
        ]
        for k in stale_generic:
            del self._generic_store[k]

    # ── 持久化（按 route 分文件）────────────────────────────────

    def save(self) -> None:
        self._compress()
        pages_dir = l2_pages_dir(self._accel_dir)
        pages_dir.mkdir(parents=True, exist_ok=True)

        routes_to_save = self._dirty_routes | {
            self._route_of_key(k) for k in self._store
        }
        now = time.time()
        for route in routes_to_save:
            prefix = f"{route}|"
            entries: dict[str, dict] = {}
            for full_key, entry in self._store.items():
                if not full_key.startswith(prefix):
                    continue
                short = full_key[len(prefix):]
                if entry.get("success_count", 0) > 0:
                    entries[short] = entry
            fp = l2_route_path(self._accel_dir, route)
            if entries:
                fp.write_text(
                    json.dumps(
                        {"version": _FILE_VERSION, "route": route, "saved_at": now, "entries": entries},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            elif fp.is_file():
                fp.unlink()

        gp = l2_generic_path(self._accel_dir)
        gp.parent.mkdir(parents=True, exist_ok=True)
        gp.write_text(
            json.dumps(
                {
                    "version": _FILE_VERSION,
                    "saved_at": now,
                    "generic_entries": self._generic_store,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._dirty_routes.clear()
