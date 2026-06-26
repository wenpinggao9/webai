"""智能加速 V3 目录布局与旧文件迁移."""
from __future__ import annotations

import json
from pathlib import Path

from core.locating.accel_paths import (
    L1_CACHE_DIR,
    L2_MEMORY_DIR,
    accel_subdir_names,
    l2_route_path,
    migrate_l2_monolith_to_routes,
    migrate_legacy_accel_layout,
    route_to_slug,
    selector_cache_path,
    selector_memory_path,
)


def test_migrate_legacy_flat_files(tmp_path):
    legacy_cache = tmp_path / "选择器缓存.json"
    legacy_memory = tmp_path / "选择器记忆库.json"
    legacy_cache.write_text(
        json.dumps({"version": 1, "entries": {"k": {"selector": "#a", "ts": 1}}}),
        encoding="utf-8",
    )
    legacy_memory.write_text(
        json.dumps({"version": 1, "page_entries": {}, "generic_entries": {}}),
        encoding="utf-8",
    )

    moved = migrate_legacy_accel_layout(tmp_path)
    assert len(moved) == 2
    assert not legacy_cache.exists()
    assert not legacy_memory.exists()
    assert selector_cache_path(tmp_path).is_file()
    assert selector_memory_path(tmp_path).is_file()
    assert selector_cache_path(tmp_path).parent.name == "L1_session"
    assert selector_memory_path(tmp_path).parent.name == "L2_pages"
    assert json.loads(selector_cache_path(tmp_path).read_text())["entries"]["k"]["selector"] == "#a"


def test_migrate_skips_when_new_path_exists(tmp_path):
    legacy = tmp_path / "选择器缓存.json"
    legacy.write_text("{}", encoding="utf-8")
    target = selector_cache_path(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_text('{"version":1,"entries":{}}', encoding="utf-8")

    moved = migrate_legacy_accel_layout(tmp_path)
    assert moved == []
    assert legacy.is_file()
    assert target.is_file()


def test_route_to_slug():
    assert route_to_slug("/video/all-question") == "video__all-question.json"
    assert route_to_slug("/") == "root.json"


def test_migrate_l2_monolith_to_routes(tmp_path):
    pages = tmp_path / "L2_pages"
    pages.mkdir(parents=True)
    monolith = pages / "selector_memory.json"
    monolith.write_text(
        json.dumps(
            {
                "version": 1,
                "saved_at": 1,
                "generic_entries": {"btn|click|提交": {"selector": ".submit", "score": 3}},
                "page_entries": {
                    "/video/all-question|click|查询": {"selector": "#q", "score": 2},
                    "/video/audit-detail|click|通过": {"selector": "#ok", "score": 1},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    moved = migrate_l2_monolith_to_routes(tmp_path)
    assert not monolith.is_file()
    assert (pages / "_generic.json").is_file()
    assert l2_route_path(tmp_path, "/video/all-question").is_file()
    assert l2_route_path(tmp_path, "/video/audit-detail").is_file()
    assert len(moved) >= 3


def test_selectors_layout_paths(tmp_path):
    selectors = tmp_path / "selectors"
    (selectors / L1_CACHE_DIR).mkdir(parents=True)
    (selectors / L2_MEMORY_DIR).mkdir(parents=True)
    assert accel_subdir_names(selectors) == ("cache", "memory", "structure")
    assert l2_route_path(selectors, "/video/all-question").parent.name == "memory"
