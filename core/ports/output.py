"""步骤㉓ 文件与输出管理.

目录结构:
  output/ui_runs/<timestamp>/<case_id>/
    ├── parsed_case.json
    ├── observability.json
    ├── execution_trace.json
    ├── planned_actions.json
    ├── semantic_dom/          (有 DOM 快照时)
    ├── screenshots/           (步骤失败时)
    └── ...
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..foundation.layout import (
    EXECUTION_LOG_FILE,
    EXECUTION_TRACE_FILE,
    LLM_RAW_JSON_FILE,
    LLM_RAW_TXT_FILE,
    OBSERVABILITY_FILE,
    OUTPUT_DIR,
    PARSED_CASE_FILE,
    PLANNED_ACTIONS_FILE,
    PROJECT_REPORTS_DIR,
    PROMPTS_USED_FILE,
    RUN_REF_FILE,
    SCREENSHOTS_SUBDIR,
    SEMANTIC_DOM_SUBDIR,
    UI_RUNS_DIR,
)

BATCH_REPORT_HTML = "report_overview.html"
BATCH_REPORT_JSON = "report_overview.json"


class FileManager:
    """管理一次测试批次的所有输出文件和用例子目录."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.batch_dir = self.root / OUTPUT_DIR / UI_RUNS_DIR / ts
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def case_dir(self, case_id: str) -> Path:
        d = self.batch_dir / _safe(case_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_parsed_case(self, case_id: str, case: Any) -> None:
        self._write_json(self.case_dir(case_id) / PARSED_CASE_FILE, _to_jsonable(case))

    def save_prompt(self, case_id: str, text: str) -> None:
        (self.case_dir(case_id) / PROMPTS_USED_FILE).write_text(text, encoding="utf-8")

    def save_raw_response(self, case_id: str, text: str) -> None:
        (self.case_dir(case_id) / LLM_RAW_TXT_FILE).write_text(text, encoding="utf-8")
        self._try_save_json(text, self.case_dir(case_id) / LLM_RAW_JSON_FILE)

    def _try_save_json(self, text: str, path: Path) -> None:
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                import json as _json
                data = _json.loads(m.group(0))
                self._write_json(path, data)
            except Exception:
                pass

    def save_planned_actions(self, case_id: str, actions: list[Any]) -> None:
        data = [a.model_dump() if hasattr(a, "model_dump") else _to_jsonable(a) for a in actions]
        self._write_json(self.case_dir(case_id) / PLANNED_ACTIONS_FILE, data)

    def save_semantic_dom(self, case_id: str, step_no: int, text: str) -> None:
        dom_dir = self.case_dir(case_id) / SEMANTIC_DOM_SUBDIR
        dom_dir.mkdir(parents=True, exist_ok=True)
        (dom_dir / f"step_{step_no:03d}.txt").write_text(text, encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Re-export for agent/runner
OBSERVABILITY_JSON = OBSERVABILITY_FILE
EXECUTION_TRACE_JSON = EXECUTION_TRACE_FILE


def publish_project_report(
    project_dir: Path,
    batch_dir: Path,
    *,
    project_root: Path | None = None,
) -> tuple[Path, Path]:
    """将批次汇总报告镜像到 business/<项目>/reports/<时间戳>/ (仅 overview + run_ref)."""
    dest = Path(project_dir) / PROJECT_REPORTS_DIR / batch_dir.name
    dest.mkdir(parents=True, exist_ok=True)

    for name in (BATCH_REPORT_JSON, BATCH_REPORT_HTML):
        src = batch_dir / name
        if src.is_file():
            shutil.copy2(src, dest / name)

    run_dir = batch_dir
    if project_root is not None:
        try:
            run_dir = batch_dir.relative_to(project_root)
        except ValueError:
            pass
    ref = {
        "batch_timestamp": batch_dir.name,
        "run_dir": str(run_dir).replace("\\", "/"),
    }
    (dest / RUN_REF_FILE).write_text(
        json.dumps(ref, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dest / BATCH_REPORT_JSON, dest / BATCH_REPORT_HTML


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items() if k != "source_path"}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj
