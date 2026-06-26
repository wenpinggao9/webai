#!/usr/bin/env python3
"""Export delivery package — cases / actions / selectors / reports.

默认自动附带最近一次（或最匹配当前项目）的 output/ui_runs 批次验收报告。

Examples:
  python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 --version 20260625-v1.0
  python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 --version v1.0 --promote-plans
  python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 --version v1.0 --no-batch
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.foundation.layout import PROJECT_REPORTS_DIR
from core.ports.business.handoff import export_delivery_package, find_batch_dir, list_case_ids
from core.ports.business.loader import _find_project_dir, _find_system_dir


def _resolve_project(path: Path) -> tuple[Path, Path]:
    p = path.resolve()
    if p.is_file():
        p = p.parent
    system = _find_system_dir(p)
    if system is None:
        raise SystemExit(f"Business system not found (missing domain_knowledge.md): {path}")
    project = _find_project_dir(p, system)
    if project is None:
        if (p / "cases").is_dir():
            project = p
        else:
            raise SystemExit(f"Project directory not found: {path}")
    return system, project


def main() -> int:
    ap = argparse.ArgumentParser(description="Export QA delivery package")
    ap.add_argument("project", help="Project dir or case file path")
    ap.add_argument("--version", required=True, help="Delivery version, e.g. 20260625-v1.0")
    ap.add_argument("--cases", default=None, help="Comma-separated case file stems (md filename without .md)")
    ap.add_argument(
        "--batch",
        default=None,
        help="Override batch dir output/ui_runs/<timestamp> (default: auto latest for project)",
    )
    ap.add_argument(
        "--no-batch",
        action="store_true",
        help="Do not attach acceptance report from output/ui_runs",
    )
    ap.add_argument(
        "--promote-plans",
        action="store_true",
        help="Promote planned_actions.json from batch to project actions/ first",
    )
    ap.add_argument("--notes", default="", help="Delivery notes")
    args = ap.parse_args()

    config_path = ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}

    system, project = _resolve_project(Path(args.project))
    case_ids = None
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(",") if c.strip()]
    else:
        case_ids = list_case_ids(project)
        if not case_ids:
            print("Warning: no cases/*.md found", file=sys.stderr)

    batch_dir = Path(args.batch).resolve() if args.batch else None
    if batch_dir and not batch_dir.is_dir():
        raise SystemExit(f"Batch directory not found: {batch_dir}")

    use_batch = not args.no_batch
    resolved_batch = None
    if use_batch:
        resolved_batch = find_batch_dir(ROOT, project, explicit=batch_dir)
        if resolved_batch is None:
            print("Warning: no output/ui_runs batch with report_overview.json found", file=sys.stderr)
        elif batch_dir is None:
            try:
                print(f"Auto batch: {resolved_batch.relative_to(ROOT)}")
            except ValueError:
                print(f"Auto batch: {resolved_batch}")

    out = export_delivery_package(
        project,
        system,
        args.version,
        project_root=ROOT,
        case_ids=case_ids,
        batch_dir=batch_dir,
        use_batch=use_batch,
        promote_plans=args.promote_plans,
        notes=args.notes,
        config=config,
    )
    print(f"Delivery package: {out}")
    print(f"  case files: {len(case_ids or [])}")
    if resolved_batch is not None:
        print(f"  reports: {out / PROJECT_REPORTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
