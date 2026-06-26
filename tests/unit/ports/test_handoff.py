"""Delivery package export."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.foundation.layout import (
    ACCEL_MEMORY_DIR,
    ACTION_PLANS_DIR,
    DOMAIN_KNOWLEDGE_FILE,
    OUTPUT_DIR,
    PLANNED_ACTIONS_FILE,
    PROJECT_ENV_FILE,
    PROJECT_REPORTS_DIR,
    SELECTORS_DIR,
    UI_RUNS_DIR,
)
from core.locating.accel_paths import L1_SESSION_DIR, L2_PAGES_DIR
from core.ports.business.handoff import (
    export_delivery_package,
    find_batch_dir,
    promote_planned_actions_from_batch,
)


def _setup_project(tmp_path: Path) -> tuple[Path, Path]:
    system = tmp_path / "vip"
    project = system / "demo"
    cases = project / "cases"
    cases.mkdir(parents=True)
    accel = system / ACCEL_MEMORY_DIR
    (accel / "L1_session").mkdir(parents=True)
    (accel / "L1_session" / "selector_cache.json").write_text('{"entries":{}}', encoding="utf-8")
    l2 = accel / "L2_pages"
    l2.mkdir(parents=True)
    (l2 / "_generic.json").write_text('{"generic_entries":{}}', encoding="utf-8")
    (l2 / "video__all-question.json").write_text('{"entries":{}}', encoding="utf-8")
    (accel / "L4_structure").mkdir(parents=True)
    (accel / "L4_structure" / "page_structure.json").write_text('{"pages":{}}', encoding="utf-8")
    (system / DOMAIN_KNOWLEDGE_FILE).write_text("---\napi_base_url: https://api.test\n---\n", encoding="utf-8")
    (project / PROJECT_ENV_FILE).write_text(
        "BASE_URL=https://ui.test\nadmin_USERNAME=10001\nadmin_VERIFY_CODE=111111\n",
        encoding="utf-8",
    )
    (cases / "case1.md").write_text("#### c1\n\n##### 步骤\n\n1. 点击\n", encoding="utf-8")
    plan_dir = project / ACTION_PLANS_DIR
    plan_dir.mkdir(parents=True)
    (plan_dir / "case1_actions.json").write_text(
        json.dumps({
            "cases": [{
                "case_id": "c1",
                "module": "vip",
                "priority": "P0",
                "origin_case": {
                    "steps": ["点击提交"],
                    "expectations": ["页面成功"],
                },
                "actions": [{"type": "click", "intent": "点击"}],
            }],
        }),
        encoding="utf-8",
    )
    return system, project


def _write_batch(project_root: Path, project: Path, *, ts: str = "20260101_120000") -> Path:
    batch = project_root / OUTPUT_DIR / UI_RUNS_DIR / ts
    batch.mkdir(parents=True)
    (batch / "report_overview.json").write_text(
        json.dumps({
            "source_file": str(project / "cases" / "case1.md"),
            "batch_timestamp": ts,
            "total_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "success_rate": "100%",
            "cases": [{
                "case_id": "c1",
                "passed": True,
                "total_steps": 1,
                "passed_steps": 1,
                "execution_time": "1.0秒",
            }],
        }),
        encoding="utf-8",
    )
    (batch / "report_overview.html").write_text("<html>ok</html>", encoding="utf-8")
    return batch


def test_export_delivery_package(tmp_path):
    system, project = _setup_project(tmp_path)
    batch = _write_batch(tmp_path, project)
    out = export_delivery_package(
        project, system, "v1.0", project_root=tmp_path, case_ids=["case1"], batch_dir=batch,
    )
    assert out.is_dir()
    assert (out / "cases" / "case1.md").is_file()
    assert (out / ACTION_PLANS_DIR / "case1_actions.json").is_file()
    assert (out / SELECTORS_DIR / "L2_pages" / "video__all-question.json").is_file()
    assert not (out / SELECTORS_DIR / L1_SESSION_DIR).exists()
    manifest = yaml.safe_load((out / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["version"] == "v1.0"
    assert manifest["case_files"][0]["file"] == "case1"
    assert manifest["case_files"][0]["has_action_plan"] is True
    assert manifest["case_files"][0]["case_count"] == 1
    assert manifest["case_files"][0]["verification"]["passed"] == 1
    assert manifest["case_files"][0]["report_html"] == f"{PROJECT_REPORTS_DIR}/case1.html"
    assert manifest["reports"][0]["file"] == "case1"
    assert "c1" not in str(manifest["case_files"][0]["description"]) or "vip" in manifest["case_files"][0]["description"]
    assert manifest["environment"]["roles"]["admin"]["username"] == "10001"
    assert manifest["reports"][0]["success_rate"] == "100%"
    assert "acceptance" not in manifest
    assert "batch" not in manifest
    assert "contents" not in manifest
    assert "accel_snapshot" not in manifest
    assert "credentials_note" not in manifest.get("environment", {})
    assert not (out / SELECTORS_DIR / "manifest.yaml").exists()


def test_find_batch_dir_auto(tmp_path):
    system, project = _setup_project(tmp_path)
    batch = _write_batch(tmp_path, project)
    found = find_batch_dir(tmp_path, project)
    assert found == batch


def test_promote_and_acceptance(tmp_path):
    system, project = _setup_project(tmp_path)
    batch = tmp_path / "batch"
    case_out = batch / "case1"
    case_out.mkdir(parents=True)
    actions = [{"intent": "新步骤", "action_type": "click"}]
    (case_out / PLANNED_ACTIONS_FILE).write_text(json.dumps(actions), encoding="utf-8")
    (batch / "report_overview.json").write_text(
        json.dumps({"total_cases": 1, "passed_cases": 1, "failed_cases": 0, "success_rate": "100%"}),
        encoding="utf-8",
    )
    (batch / "report_overview.html").write_text("<html>ok</html>", encoding="utf-8")

    promoted = promote_planned_actions_from_batch(project, batch, ["case1"])
    assert promoted == ["case1"]
    plan = json.loads((project / ACTION_PLANS_DIR / "case1.json").read_text(encoding="utf-8"))
    assert plan[0]["intent"] == "新步骤"

    out = export_delivery_package(
        project, system, "v1.1", project_root=tmp_path, case_ids=["case1"], batch_dir=batch,
    )
    assert (out / PROJECT_REPORTS_DIR / "case1.html").is_file()
    assert not (out / "acceptance").exists()
    manifest = yaml.safe_load((out / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["reports"][0]["success_rate"] == "100%"
    assert manifest["reports"][0]["report_html"] == f"{PROJECT_REPORTS_DIR}/case1.html"
