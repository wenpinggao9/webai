"""智能加速层落盘路径 + 旧版布局迁移 + L2 按 route 分文件."""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from ..foundation.layout import SELECTORS_DIR, first_existing

logger = logging.getLogger(__name__)

L1_SESSION_DIR = "L1_session"
L2_PAGES_DIR = "L2_pages"
L4_STRUCTURE_DIR = "L4_structure"

L1_CACHE_DIR = "cache"
L2_MEMORY_DIR = "memory"
L4_STRUCTURE_SHORT_DIR = "structure"

SELECTOR_CACHE_FILE = "selector_cache.json"
SELECTOR_MEMORY_FILE = "selector_memory.json"
L2_GENERIC_FILE = "_generic.json"
PAGE_STRUCTURE_FILE = "page_structure.json"
PAGE_STRUCTURE_LEGACY_FILE = "page_structure_learner.json"

_LEGACY_V3_CACHE_DIR = "selector_cache"
_LEGACY_V3_MEMORY_DIR = "selector_memory"
_LEGACY_V3_STRUCTURE_DIR = "page_structure_learner"
_LEGACY_SELECTOR_CACHE = "选择器缓存.json"
_LEGACY_SELECTOR_MEMORY = "选择器记忆库.json"


def accel_subdir_names(accel_dir: str | Path) -> tuple[str, str, str]:
    """按业务目录实际布局解析 L1/L2/L4 子目录名（新旧均兼容）."""
    root = Path(accel_dir)
    if root.name == SELECTORS_DIR:
        return L1_CACHE_DIR, L2_MEMORY_DIR, L4_STRUCTURE_SHORT_DIR
    if first_existing(root, L1_CACHE_DIR, L2_MEMORY_DIR, L4_STRUCTURE_SHORT_DIR):
        return (
            (first_existing(root, L1_CACHE_DIR) or root / L1_CACHE_DIR).name,
            (first_existing(root, L2_MEMORY_DIR) or root / L2_MEMORY_DIR).name,
            (
                first_existing(root, L4_STRUCTURE_SHORT_DIR)
                or root / L4_STRUCTURE_SHORT_DIR
            ).name,
        )
    return L1_SESSION_DIR, L2_PAGES_DIR, L4_STRUCTURE_DIR


def l1_session_dir(accel_dir: str | Path) -> Path:
    name, _, _ = accel_subdir_names(accel_dir)
    return Path(accel_dir) / name


def l2_pages_dir(accel_dir: str | Path) -> Path:
    _, name, _ = accel_subdir_names(accel_dir)
    return Path(accel_dir) / name


def l4_structure_dir(accel_dir: str | Path) -> Path:
    _, _, name = accel_subdir_names(accel_dir)
    return Path(accel_dir) / name


def selector_cache_path(accel_dir: str | Path) -> Path:
    return l1_session_dir(accel_dir) / SELECTOR_CACHE_FILE


def selector_memory_path(accel_dir: str | Path) -> Path:
    """旧版 L2 单文件路径（仅用于迁移检测）."""
    return l2_pages_dir(accel_dir) / SELECTOR_MEMORY_FILE


def l2_generic_path(accel_dir: str | Path) -> Path:
    return l2_pages_dir(accel_dir) / L2_GENERIC_FILE


def route_to_slug(route: str) -> str:
    """ /video/all-question → video__all-question.json """
    r = (route or "/").strip()
    if not r.startswith("/"):
        r = "/" + r
    if r in ("/", ""):
        slug = "root"
    else:
        slug = r.strip("/").replace("/", "__")
    slug = re.sub(r"[^\w\-]", "_", slug)
    return f"{slug}.json"


def l2_route_path(accel_dir: str | Path, route: str) -> Path:
    return l2_pages_dir(accel_dir) / route_to_slug(route)


def page_structure_path(accel_dir: str | Path) -> Path:
    return l4_structure_dir(accel_dir) / PAGE_STRUCTURE_FILE


def page_structure_legacy_path(accel_dir: str | Path) -> Path:
    return l4_structure_dir(accel_dir) / PAGE_STRUCTURE_LEGACY_FILE


def _is_l2_dir(name: str) -> bool:
    return name in (L2_PAGES_DIR, L2_MEMORY_DIR)


def resolve_accel_dir_from_memory_arg(path_or_dir: str | Path) -> Path:
    """SelectorMemory 构造参数 → 加速记忆根目录."""
    p = Path(path_or_dir)
    if p.is_dir():
        l1, l2, _ = accel_subdir_names(p)
        if (p / l1).is_dir() or (p / l2).is_dir():
            return p
        if _is_l2_dir(p.name):
            return p.parent
        return p
    if _is_l2_dir(p.parent.name):
        return p.parent.parent
    return p.parent


def split_l2_monolith(data: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    """page_entries → (generic_entries, route → {entry_key → entry})."""
    page_entries = data.get("page_entries", {})
    if not page_entries and "version" not in data:
        page_entries = {k: v for k, v in data.items() if isinstance(v, dict)}

    generic = dict(data.get("generic_entries") or {})
    by_route: dict[str, dict[str, dict]] = {}

    for full_key, entry in page_entries.items():
        if not isinstance(entry, dict):
            continue
        parts = str(full_key).split("|", 2)
        if len(parts) < 3:
            continue
        route, action_type, intent = parts[0], parts[1], parts[2]
        short_key = f"{action_type}|{intent}"
        by_route.setdefault(route, {})[short_key] = entry

    return generic, by_route


def migrate_l2_monolith_to_routes(accel_dir: str | Path) -> list[str]:
    """将 L2_pages/selector_memory.json 拆分为按 route 的多文件."""
    root = Path(accel_dir)
    monolith = selector_memory_path(root)
    if not monolith.is_file():
        return []

    try:
        data = json.loads(monolith.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("L2 单文件解析失败: %s", exc)
        return []

    generic, by_route = split_l2_monolith(data)
    pages_dir = l2_pages_dir(root)
    pages_dir.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []

    if generic:
        gp = l2_generic_path(root)
        if not gp.is_file():
            gp.write_text(
                json.dumps(
                    {"version": 1, "generic_entries": generic, "saved_at": data.get("saved_at")},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            moved.append(str(gp.relative_to(root)))

    for route, entries in by_route.items():
        target = l2_route_path(root, route)
        if target.is_file():
            continue
        target.write_text(
            json.dumps(
                {
                    "version": 1,
                    "route": route,
                    "saved_at": data.get("saved_at"),
                    "entries": entries,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        moved.append(str(target.relative_to(root)))

    if moved:
        backup = monolith.with_suffix(".json.bak")
        shutil.move(str(monolith), str(backup))
        moved.append(f"{monolith.name} → {backup.name}")
        logger.info("L2 已按 route 拆分: %d 个文件", len(moved))
    return moved


def migrate_legacy_accel_layout(accel_dir: str | Path) -> list[str]:
    root = Path(accel_dir)
    moved: list[str] = []

    pairs = (
        (root / _LEGACY_SELECTOR_CACHE, selector_cache_path(root)),
        (root / _LEGACY_SELECTOR_MEMORY, selector_memory_path(root)),
        (root / _LEGACY_V3_CACHE_DIR / SELECTOR_CACHE_FILE, selector_cache_path(root)),
        (root / _LEGACY_V3_MEMORY_DIR / SELECTOR_MEMORY_FILE, selector_memory_path(root)),
        (root / _LEGACY_V3_STRUCTURE_DIR / PAGE_STRUCTURE_LEGACY_FILE, page_structure_legacy_path(root)),
        (root / _LEGACY_V3_STRUCTURE_DIR / PAGE_STRUCTURE_FILE, page_structure_path(root)),
        (page_structure_legacy_path(root), page_structure_path(root)),
    )
    for legacy, target in pairs:
        if not legacy.is_file():
            continue
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(target))
        try:
            rel = legacy.relative_to(root)
        except ValueError:
            rel = legacy.name
        moved.append(f"{rel} → {target.relative_to(root)}")

    moved.extend(migrate_l2_monolith_to_routes(root))
    return moved
