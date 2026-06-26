"""动作规划：business/<project>/actions/<用例文件名>_actions.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from ...foundation.layout import ACTIONS_DIR, action_plans_path
from ...pipeline.planning import PlannedAction, coerce_action

logger = logging.getLogger(__name__)

PLAN_DIR_NAME = ACTIONS_DIR
CASE_FILE_ACTIONS_SUFFIX = "_actions.json"


def plan_dir_name(project_dir: Path | None = None) -> str:
    if project_dir is not None:
        return action_plans_path(project_dir).name
    return PLAN_DIR_NAME


def action_plans_dir(project_dir: Path) -> Path:
    return action_plans_path(project_dir)


def case_file_actions_path(project_dir: Path, case_file_stem: str) -> Path:
    """用例 Markdown 文件名（不含 .md）对应的规划文件路径."""
    return action_plans_dir(project_dir) / f"{case_file_stem}{CASE_FILE_ACTIONS_SUFFIX}"


def planned_actions_path(project_dir: Path, case_id: str) -> Path:
    """兼容旧路径 <case_id>.json（不再由 run.py 自动读写）."""
    return action_plans_dir(project_dir) / f"{case_id}.json"


def dump_action_for_file(action: Any) -> dict[str, Any]:
    if hasattr(action, "model_dump"):
        raw = action.model_dump()
    elif isinstance(action, dict):
        raw = dict(action)
    else:
        raw = {"type": getattr(action, "type", ""), "intent": getattr(action, "intent", "")}
    d: dict[str, Any] = {"type": raw.get("type"), "intent": raw.get("intent")}
    if raw.get("value") is not None:
        d["value"] = raw.get("value")
    extras = raw.get("extras") or {}
    if extras:
        d["extras"] = extras
    if raw.get("negate"):
        d["negate"] = True
    return d


def build_plan_entry(case: Any, origin_case: dict[str, Any], actions: list[Any]) -> dict[str, Any]:
    module = case.resolved_module if hasattr(case, "resolved_module") else ""
    priority = getattr(case, "priority", "") or ""
    return {
        "case_id": case.case_id,
        "module": module,
        "priority": priority,
        "origin_case": origin_case,
        "actions": [dump_action_for_file(a) for a in actions],
    }


def save_case_file_actions(project_dir: Path, case_file_stem: str, entries: list[dict[str, Any]]) -> Path:
    """将一次 run 的规划结果写入 actions/<stem>_actions.json（覆盖整文件）."""
    out_dir = action_plans_dir(project_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = case_file_actions_path(project_dir, case_file_stem)
    payload = {"cases": entries}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_case_file_actions(project_dir: Path | None, case_file_stem: str) -> Optional[dict[str, Any]]:
    if project_dir is None or not case_file_stem:
        return None
    path = case_file_actions_path(project_dir, case_file_stem)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("动作规划文件解析失败 %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def load_preplanned_map_for_file(
    project_dir: Path | None,
    case_file_stem: str,
) -> dict[str, list[PlannedAction]]:
    """从 <stem>_actions.json 加载 case_id → 动作列表映射."""
    data = load_case_file_actions(project_dir, case_file_stem)
    if not data:
        return {}
    cases = data.get("cases")
    if not isinstance(cases, list):
        return {}
    out: dict[str, list[PlannedAction]] = {}
    for item in cases:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        raw_actions = item.get("actions")
        if not case_id or not isinstance(raw_actions, list):
            continue
        actions: list[PlannedAction] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            act = coerce_action(raw)
            if act is not None:
                actions.append(act)
        if actions:
            out[case_id] = actions
    return out


def load_planned_actions(project_dir: Path | None, case_id: str) -> Optional[list[PlannedAction]]:
    """兼容：读取旧版 actions/<case_id>.json（run.py 默认不再调用）."""
    if project_dir is None or not case_id:
        return None
    path = planned_actions_path(project_dir, case_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("动作规划 JSON 解析失败 %s: %s", path, exc)
        return None
    if not isinstance(raw, list):
        return None
    actions: list[PlannedAction] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        act = coerce_action(item)
        if act is not None:
            actions.append(act)
    return actions or None


def save_planned_actions(project_dir: Path, case_id: str, actions: list[Any]) -> Path:
    """兼容：写入旧版 actions/<case_id>.json."""
    out_dir = action_plans_dir(project_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{case_id}.json"
    data = [
        a.model_dump() if hasattr(a, "model_dump") else a
        for a in actions
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
