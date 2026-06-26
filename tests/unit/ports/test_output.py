"""output: 业务报告镜像."""
from __future__ import annotations

import json
from pathlib import Path

from core.foundation.layout import PROJECT_REPORTS_DIR, RUN_REF_FILE
from core.ports.output import BATCH_REPORT_HTML, BATCH_REPORT_JSON, publish_project_report


def test_publish_project_report_copies_overview_and_run_ref(tmp_path: Path) -> None:
    project = tmp_path / "business" / "sys" / "proj"
    project.mkdir(parents=True)
    batch = tmp_path / "output" / "ui_runs" / "20260625_120000"
    batch.mkdir(parents=True)
    (batch / BATCH_REPORT_JSON).write_text('{"type": "batch_overview"}', encoding="utf-8")
    (batch / BATCH_REPORT_HTML).write_text("<html>ok</html>", encoding="utf-8")

    json_path, html_path = publish_project_report(
        project, batch, project_root=tmp_path,
    )

    dest = project / PROJECT_REPORTS_DIR / "20260625_120000"
    assert json_path == dest / BATCH_REPORT_JSON
    assert html_path == dest / BATCH_REPORT_HTML
    assert json.loads((dest / RUN_REF_FILE).read_text(encoding="utf-8")) == {
        "batch_timestamp": "20260625_120000",
        "run_dir": "output/ui_runs/20260625_120000",
    }
