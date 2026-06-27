"""upload 动作: value 解析为本地文件路径."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.pipeline.parser.schema import CaseResource
from core.pipeline.planning import PlannedAction
from core.resources import ResourceManager
from core.runtime.execution.dispatcher import ActionDispatcher


def test_dispatcher_resolves_upload_alias_to_file_path():
    root = Path(__file__).resolve().parents[3]
    rm = ResourceManager(root)
    rm.set_project_asset_dir(root / "business/tiku/tiku_video/大学增加前审/resources")
    d = ActionDispatcher(
        page=MagicMock(),
        resolver=MagicMock(),
        resource_manager=rm,
        case_resources={
            "录制视频": CaseResource(name="录制视频", source="资产", filename="vip2.mp4"),
        },
    )
    action = PlannedAction(type="upload", intent="上传录制视频", value="录制视频")
    path, err = d._resolve_upload_path(action)
    assert err is None
    assert path.endswith("vip2.mp4")
    assert Path(path).is_file()


def test_dispatcher_upload_missing_resource_returns_error():
    d = ActionDispatcher(
        page=MagicMock(),
        resolver=MagicMock(),
        resource_manager=ResourceManager(Path(__file__).resolve().parents[3]),
    )
    action = PlannedAction(type="upload", intent="上传", value="not_a_real_file.mp4")
    path, err = d._resolve_upload_path(action)
    assert path == ""
    assert err and "找不到上传资源" in err
