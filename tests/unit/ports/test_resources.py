"""ResourceManager: 项目 resources 扫描与 upload 路径解析."""
from __future__ import annotations

from pathlib import Path

from core.pipeline.parser.schema import CaseResource
from core.resources import ResourceManager


def test_resolve_filename_in_project_resources_dir():
    root = Path(__file__).resolve().parents[3]
    rm = ResourceManager(root)
    project_res = root / "business/tiku/tiku_video/大学增加前审/resources"
    rm.set_project_asset_dir(project_res)
    path = rm.resolve_upload("vip2.mp4")
    assert path is not None
    assert path.endswith("vip2.mp4")
    assert Path(path).is_file()


def test_resolve_resource_alias_via_case_resources():
    root = Path(__file__).resolve().parents[3]
    rm = ResourceManager(root)
    project_res = root / "business/tiku/tiku_video/大学增加前审/resources"
    rm.set_project_asset_dir(project_res)
    case_resources = {
        "录制视频": CaseResource(name="录制视频", source="资产", filename="vip2.mp4"),
    }
    path = rm.resolve_upload("录制视频", case_resources)
    assert path is not None
    assert path.endswith("vip2.mp4")


def test_discover_deep_business_resources_without_project_dir():
    root = Path(__file__).resolve().parents[3]
    rm = ResourceManager(root)
    dirs = [str(d) for d in rm.asset_dirs]
    assert any("大学增加前审/resources" in d for d in dirs)
