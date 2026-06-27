"""步骤⑳ 资源管理 —— 上传文件从哪来.

三种来源:
  上传(上传)  → API 临时文件目录
  本地(本地)  → 绝对路径
  资产(资产)  → 在多个资产目录中搜索文件名
自动注入: 上传步骤但无资源时, 注入默认资源.
临时文件清理: 任务结束后删除.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..foundation.layout import (
    BUSINESS_DIR,
    LEGACY_BUSINESS_DIR,
    LEGACY_TEST_RESOURCES_DIR,
    RESOURCES_DIR,
    TEST_RESOURCES_DIR,
)
from ..pipeline.parser import CaseResource


def _discover_business_resource_dirs(root: Path) -> list[Path]:
    """扫描 business 下各层项目 resources/ 目录 (1~4 级子路径)."""
    resource_dir_names = (RESOURCES_DIR, TEST_RESOURCES_DIR, LEGACY_TEST_RESOURCES_DIR)
    found: list[Path] = []
    seen: set[Path] = set()
    for biz_name in (BUSINESS_DIR, LEGACY_BUSINESS_DIR):
        for res_name in resource_dir_names:
            for depth in ("*", "*/*", "*/*/*", "*/*/*/*"):
                pattern = f"{biz_name}/{depth}/{res_name}"
                for d in root.glob(pattern):
                    if d.is_dir() and d not in seen:
                        seen.add(d)
                        found.append(d)
    return found


class ResourceManager:
    """统一解析用例资源名、上传临时文件、本地路径和项目资产文件."""

    def __init__(self, project_root: str | Path, upload_dir: Optional[str | Path] = None) -> None:
        self.root = Path(project_root)
        self.upload_dir = Path(upload_dir) if upload_dir else self.root / "uploads"
        # 兼容中文/英文资产目录命名, 降低项目接入成本.
        self.asset_dirs = [
            self.root / "assets",
            self.root / RESOURCES_DIR,
            self.root / TEST_RESOURCES_DIR,
            self.root / LEGACY_TEST_RESOURCES_DIR,
        ]
        self.asset_dirs.extend(_discover_business_resource_dirs(self.root))
        self._project_asset_dir: Optional[Path] = None
        self._temp_files: list[Path] = []

    def set_project_asset_dir(self, path: str | Path | None) -> None:
        """当前业务项目 resources/ 优先于全局扫描目录."""
        if path is None:
            self._project_asset_dir = None
            return
        p = Path(path)
        self._project_asset_dir = p if p.is_dir() else None

    def _asset_search_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self._project_asset_dir is not None:
            dirs.append(self._project_asset_dir)
        dirs.extend(self.asset_dirs)
        return dirs

    def resolve(self, name_or_path: str, case_resources: Optional[dict[str, CaseResource]] = None) -> Optional[str]:
        """把资源名/路径解析为真实文件绝对路径; 找不到返回 None."""
        case_resources = case_resources or {}
        # 1. 用例定义的资源名
        res = case_resources.get(name_or_path)
        if res is not None:
            return self._resolve_resource(res)
        # 2. 直接是存在的路径
        p = Path(name_or_path)
        if p.is_absolute() and p.exists():
            return str(p)
        if (self.root / name_or_path).exists():
            return str(self.root / name_or_path)
        # 3. 在资产目录里按文件名搜
        return self._search_assets(name_or_path)

    def _resolve_resource(self, res: CaseResource) -> Optional[str]:
        """按资源来源类型解析为真实文件路径."""
        if res.source == "上传":
            cand = self.upload_dir / res.filename
            return str(cand) if cand.exists() else None
        if res.source == "本地":
            p = Path(res.filename)
            return str(p) if p.exists() else None
        if res.source == "资产":
            return self._search_assets(res.filename)
        return None

    def _search_assets(self, filename: str) -> Optional[str]:
        """在预设资产目录中按文件名查找资源."""
        for d in self._asset_search_dirs():
            cand = d / filename
            if cand.exists():
                return str(cand.resolve())
        return None

    def resolve_upload(
        self,
        value: str,
        case_resources: Optional[dict[str, CaseResource]] = None,
    ) -> Optional[str]:
        """解析 upload 动作的 value (资源别名/文件名) 为本地文件绝对路径."""
        raw = (value or "").strip()
        if not raw:
            return self.default_resource()
        return self.resolve(raw, case_resources)

    def default_resource(self) -> str:
        """上传步骤无资源时的默认文件 (即时生成一个临时 txt)."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        default = self.upload_dir / "_default_upload.txt"
        if not default.exists():
            default.write_text("UI 自动化默认上传文件\n", encoding="utf-8")
            self._temp_files.append(default)
        return str(default)

    def cleanup(self) -> None:
        """清理本次运行生成的临时默认上传文件."""
        for f in self._temp_files:
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass
        self._temp_files.clear()
