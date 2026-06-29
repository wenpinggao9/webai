"""Report HTML failure screenshot buttons."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.foundation.layout import SCREENSHOTS_SUBDIR
from core.ports.report import (
    _generate_batch_html,
    build_report_data,
    generate_html_report,
    save_batch_overview,
)


@dataclass
class _FakeResult:
    step_no: int
    raw_text: str
    action: str
    status: str
    duration_ms: int = 0
    error: str | None = None
    screenshot: str | None = None
    message: str | None = None
    selector: str | None = None
    locator_repr: str | None = None
    resolved_html: str | None = None
    dispatch_ok: bool | None = True
    post_check_ok: bool | None = True
    post_check_reason: str | None = None
    optional_skipped: bool = False
    post_retries: list | None = None


def test_build_report_data_includes_screenshot_on_failed_step(tmp_path):
    shot = tmp_path / SCREENSHOTS_SUBDIR / "step_001_fail.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(b"png")

    results = [
        _FakeResult(1, "点击提交", "click", "PASS"),
        _FakeResult(2, "断言失败", "assert", "FAIL", error="timeout", screenshot=shot),
    ]
    data = build_report_data("c1", results, 1000, out_dir=tmp_path)
    assert data["details"][1]["screenshot"] == f"{SCREENSHOTS_SUBDIR}/step_001_fail.png"
    assert data["details"][0].get("screenshot") in ("", None)


def test_case_html_has_view_screenshot_button(tmp_path):
    shot = tmp_path / SCREENSHOTS_SUBDIR / "step_002_fail.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(b"png")

    results = [_FakeResult(2, "点按钮", "click", "FAIL", screenshot=shot, message="未找到")]
    data = build_report_data("c1", results, 500, out_dir=tmp_path)
    html = generate_html_report(data, {})
    assert "查看截图" in html
    assert "shot-open-btn" in html
    assert f'data-shot-src="../{SCREENSHOTS_SUBDIR}/step_002_fail.png"' in html
    assert 'onclick="openShotModal(' not in html


def test_batch_html_has_view_screenshot_button(tmp_path):
    batch = tmp_path / "batch"
    case_dir = batch / "c1" / SCREENSHOTS_SUBDIR
    case_dir.mkdir(parents=True)
    shot = case_dir / "step_001_fail.png"
    shot.write_bytes(b"png")

    case_results = [{
        "case_id": "c1",
        "passed": False,
        "total_steps": 1,
        "passed_steps": 0,
        "failed_steps": 1,
        "step_success_rate": "0%",
        "execution_time": "1s",
        "details": [{
            "step": "步骤1: click",
            "success": False,
            "message": "失败",
            "screenshot": f"c1/{SCREENSHOTS_SUBDIR}/step_001_fail.png",
        }],
    }]
    save_batch_overview(
        batch,
        source_file="cases/x.md",
        case_results=case_results,
        watermark_cfg={},
    )
    html = (batch / "report_overview.html").read_text(encoding="utf-8")
    assert "查看截图" in html
    assert "shot-open-btn" in html
    assert f'data-shot-src="c1/{SCREENSHOTS_SUBDIR}/step_001_fail.png"' in html
    assert 'onclick="openShotModal(' not in html


def test_screenshot_button_survives_apostrophe_in_step_label(tmp_path):
    from core.ports.report import _screenshot_button_html

    btn = _screenshot_button_html(
        f"{SCREENSHOTS_SUBDIR}/step_001_fail.png",
        prefix="case_a/",
        step_label="步骤2: 点击'审核行为'下拉框",
    )
    assert "shot-open-btn" in btn
    assert "data-shot-src=" in btn
    assert "onclick=" not in btn


def test_case_screenshot_rel_strips_absolute_path(tmp_path):
    from core.ports.report import _case_screenshot_rel

    case_dir = tmp_path / "vip_前审_012"
    shot = case_dir / SCREENSHOTS_SUBDIR / "step_006_fail.png"
    shot.parent.mkdir(parents=True)
    rel = _case_screenshot_rel(shot, case_dir)
    assert rel == f"{SCREENSHOTS_SUBDIR}/step_006_fail.png"


def test_handoff_copies_screenshots_with_report(tmp_path):
    from core.ports.business.handoff import export_delivery_package

    system = tmp_path / "sys"
    project = system / "proj"
    cases = project / "cases"
    cases.mkdir(parents=True)
    (cases / "case1.md").write_text("# c1\n", encoding="utf-8")
    (system / "domain_knowledge.md").write_text("---\napi_base_url: https://x\n---\n", encoding="utf-8")

    batch = tmp_path / "output" / "ui_runs" / "20260101_120000"
    shot_dir = batch / "c1" / SCREENSHOTS_SUBDIR
    shot_dir.mkdir(parents=True)
    (shot_dir / "step_001_fail.png").write_bytes(b"png")

    overview = {
        "source_file": str(project / "cases" / "case1.md"),
        "total_cases": 1,
        "passed_cases": 0,
        "failed_cases": 1,
        "success_rate": "0%",
        "cases": [{
            "case_id": "c1",
            "passed": False,
            "details": [{
                "step": "步骤1",
                "success": False,
                "message": "err",
                "screenshot": f"{SCREENSHOTS_SUBDIR}/step_001_fail.png",
            }],
        }],
    }
    (batch / "report_overview.json").write_text(json.dumps(overview), encoding="utf-8")
    (batch / "report_overview.html").write_text("<html>ok</html>", encoding="utf-8")

    out = export_delivery_package(
        project, system, "v1", project_root=tmp_path, case_ids=["case1"], batch_dir=batch,
    )
    copied = out / "reports" / "c1" / SCREENSHOTS_SUBDIR / "step_001_fail.png"
    assert copied.is_file()
