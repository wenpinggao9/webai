"""业务级智能加速目录：business/<system>/accel_memory/."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ...foundation.layout import (
    ACCEL_MEMORY_DIR,
    LEGACY_ACCEL_MEMORY_DIR,
    LEGACY_GLOBAL_ACCEL_DIR,
    SELECTORS_DIR,
    accel_memory_path,
    first_existing,
)
from ...locating.accel_paths import (
    migrate_legacy_accel_layout,
    selector_cache_path,
    selector_memory_path,
)

logger = logging.getLogger(__name__)

ACCEL_DIR_NAME = SELECTORS_DIR


def business_accel_dir(system_dir: Path) -> Path:
    return accel_memory_path(system_dir)


def resolve_accel_dir(
    system_dir: Path | None,
    project_root: Path,
) -> Path:
    """优先 business/<system>/accel_memory/，否则回退项目根 legacy_accel/."""
    if system_dir is not None:
        accel = business_accel_dir(system_dir)
        accel.mkdir(parents=True, exist_ok=True)
        return accel
    legacy = Path(project_root) / LEGACY_GLOBAL_ACCEL_DIR
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy


def seed_business_accel_from_global(
    global_accel: Path,
    business_accel: Path,
) -> list[str]:
    """业务加速目录为空时，从全局 legacy 目录复制已有数据（一次性）."""
    migrated_layout = migrate_legacy_accel_layout(business_accel)
    actions: list[str] = list(migrated_layout)

    if not global_accel.is_dir():
        return actions

    pairs = (
        (selector_cache_path(global_accel), selector_cache_path(business_accel)),
        (selector_memory_path(global_accel), selector_memory_path(business_accel)),
    )
    for src, dst in pairs:
        if not src.is_file():
            continue
        if dst.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        actions.append(f"{src.name} → {business_accel.name}/")
        logger.info("Accel memory copied from global: %s → %s", src, dst)
    return actions
