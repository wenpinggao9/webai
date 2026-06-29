"""研发 → QA 交付包导出：冻结 cases / actions / selectors / reports."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from ...foundation.layout import (
    ACCEL_MEMORY_DIR,
    CASES_DIR,
    DELIVERY_DIR,
    LEGACY_DELIVERY_DIR,
    PROJECT_REPORTS_DIR,
    SCREENSHOTS_SUBDIR,
    SELECTORS_DIR,
    accel_memory_path,
    find_direction_dir,
    first_existing,
    planned_actions_file,
    ui_runs_root,
)
from ...locating.accel_paths import (
    accel_subdir_names,
    l1_session_dir,
    l2_pages_dir,
    l4_structure_dir,
)
from .env import resolve_project_runtime
from .plan_store import action_plans_dir, plan_dir_name, planned_actions_path, save_planned_actions

logger = logging.getLogger(__name__)

HANDOFF_DIR_NAME = DELIVERY_DIR
CASES_DIR_NAME = CASES_DIR
ACCEL_DIR_NAME = ACCEL_MEMORY_DIR

_L2_SKIP_SUFFIXES = (".bak",)
_L2_SKIP_NAMES = {"selector_memory.json"}

_DEFAULT_DELIVERY_ACCEL = {"include_l1": False, "include_l2": True, "include_l4": True}


def delivery_accel_policy(config: dict[str, Any] | None = None) -> dict[str, bool]:
    """从 config.yaml delivery.accel 读取交付包加速层策略；缺省 L2+L4，不含 L1."""
    accel = ((config or {}).get("delivery") or {}).get("accel") or {}
    return {
        "include_l1": bool(accel.get("include_l1", _DEFAULT_DELIVERY_ACCEL["include_l1"])),
        "include_l2": bool(accel.get("include_l2", _DEFAULT_DELIVERY_ACCEL["include_l2"])),
        "include_l4": bool(accel.get("include_l4", _DEFAULT_DELIVERY_ACCEL["include_l4"])),
    }


def delivery_dir(project_dir: Path, version: str) -> Path:
    base = first_existing(project_dir, DELIVERY_DIR, LEGACY_DELIVERY_DIR)
    root = base or (project_dir / DELIVERY_DIR)
    return root / version


def list_case_ids(project_dir: Path, *, include_draft: bool = False) -> list[str]:
    cases_root = Path(project_dir) / CASES_DIR_NAME
    if not cases_root.is_dir():
        return []
    ids: list[str] = []
    for p in sorted(cases_root.glob("*.md")):
        if not include_draft and p.parent.name == "_draft":
            continue
        if p.name.startswith("."):
            continue
        ids.append(p.stem)
    return ids


def _batch_source_stem(batch_dir: Path) -> str:
    src = str(_load_batch_overview(batch_dir).get("source_file") or "").replace("\\", "/")
    return Path(src).stem if src else ""


def _project_batch_score(project_dir: Path, source_file: str) -> int:
    project_name = project_dir.name
    project_tail = str(project_dir).replace("\\", "/")
    src = source_file.replace("\\", "/")
    if project_name in src or project_tail.endswith(src.lstrip("/")) or src in project_tail:
        return 3
    if project_dir.parent.name and project_dir.parent.name in src:
        return 1
    return 0


def find_report_batches(
    project_root: Path,
    project_dir: Path,
    case_stems: list[str],
    *,
    explicit: Path | None = None,
) -> dict[str, Path]:
    """每个用例文件 stem → 最近一次匹配项目的跑测批次."""
    stems = set(case_stems)
    latest: dict[str, tuple[int, str, Path]] = {}

    def consider(batch: Path) -> None:
        data = _load_batch_overview(batch)
        if not data:
            return
        src = str(data.get("source_file") or "").replace("\\", "/")
        stem = Path(src).stem
        if not stem or stem not in stems:
            return
        score = _project_batch_score(project_dir, src)
        if score == 0:
            return
        prev = latest.get(stem)
        ts = batch.name
        if prev is None or ts > prev[1]:
            latest[stem] = (score, ts, batch)

    runs_root = ui_runs_root(Path(project_root))
    if runs_root.is_dir():
        for batch in runs_root.iterdir():
            if batch.is_dir():
                consider(batch)

    if explicit is not None and explicit.is_dir():
        stem = _batch_source_stem(explicit)
        if stem not in stems and len(stems) == 1:
            stem = next(iter(stems))
        if stem in stems:
            latest[stem] = (4, explicit.name, explicit)

    return {stem: batch for stem, (_, _, batch) in latest.items()}


def find_batch_dir(
    project_root: Path,
    project_dir: Path,
    *,
    explicit: Path | None = None,
) -> Path | None:
    """解析验收批次目录：显式指定 > 匹配项目的最近批次 > 全局最近批次."""
    if explicit is not None:
        return explicit if explicit.is_dir() else None

    runs_root = ui_runs_root(Path(project_root))
    if not runs_root.is_dir():
        return None

    project_name = project_dir.name
    project_tail = str(project_dir).replace("\\", "/")
    candidates: list[tuple[int, str, Path]] = []

    for batch in runs_root.iterdir():
        if not batch.is_dir():
            continue
        overview_path = batch / "report_overview.json"
        if not overview_path.is_file():
            continue
        score = 0
        try:
            data = json.loads(overview_path.read_text(encoding="utf-8"))
            src = str(data.get("source_file") or "").replace("\\", "/")
            if project_name in src or project_tail.endswith(src.lstrip("/")) or src in project_tail:
                score = 3
            elif project_dir.parent.name and project_dir.parent.name in src:
                score = 1
        except Exception:
            pass
        candidates.append((score, batch.name, batch))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _load_batch_overview(batch_dir: Path | None) -> dict[str, Any]:
    if batch_dir is None:
        return {}
    overview = batch_dir / "report_overview.json"
    if not overview.is_file():
        return {}
    try:
        data = json.loads(overview.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("解析批次报告失败: %s", exc)
        return {}


def _roles_for_manifest(roles: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name in sorted(roles):
        cfg = roles[name]
        entry = {
            k: str(v)
            for k, v in cfg.items()
            if k in ("username", "verify_code", "password") and str(v).strip()
        }
        if entry:
            out[name] = entry
    return out



def _parse_md_verify_hints(md_path: Path, *, limit: int = 3) -> list[str]:
    """从用例 md 提取验证点/标题作为功能描述补充."""
    if not md_path.is_file():
        return []
    hints: list[str] = []
    section: str | None = None
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("##### "):
            title = line[6:].strip()
            if title in ("验证点", "操作步骤", "预期结果"):
                section = title
                continue
            if title.startswith("用例ID"):
                section = "case_id"
                continue
            if section == "验证点":
                section = None
        if section == "验证点" and line and not line.startswith("#"):
            text = line.lstrip("-*0123456789. ").strip()
            if text and text not in hints:
                hints.append(text[:80])
            if len(hints) >= limit:
                break
    return hints


def _describe_case_file(
    stem: str,
    plan_items: list[dict[str, Any]],
    md_path: Path,
) -> str:
    """一句话说明该用例文件主要测什么."""
    if not plan_items:
        hints = _parse_md_verify_hints(md_path)
        if hints:
            return f"{'；'.join(hints)}（仅 md，无 actions 规划）"
        return "仅打包用例 Markdown，尚无 actions 规划"

    modules = sorted({str(x.get("module") or "").strip() for x in plan_items if x.get("module")})
    themes: list[str] = []
    seen: set[str] = set()
    for item in plan_items:
        origin = item.get("origin_case") if isinstance(item.get("origin_case"), dict) else {}
        steps = origin.get("steps") or []
        if not steps:
            continue
        head = str(steps[0]).strip()[:56]
        if head and head not in seen:
            seen.add(head)
            themes.append(head)
        if len(themes) >= 3:
            break

    mod_part = "、".join(modules) if modules else stem
    if themes:
        return f"{mod_part}：{'；'.join(themes)}（共{len(plan_items)}条用例）"
    hints = _parse_md_verify_hints(md_path, limit=2)
    if hints:
        return f"{mod_part}：{'；'.join(hints)}（共{len(plan_items)}条用例）"
    return f"{mod_part}（共{len(plan_items)}条用例，详见 actions）"


def _verification_for_file(
    stem: str,
    plan_items: list[dict[str, Any]],
    batch_dir: Path | None,
    *,
    report_html: str = "",
) -> dict[str, Any] | None:
    """若本文件有跑测报告，返回汇总验收结果."""
    if batch_dir is None or not plan_items:
        return None

    batch_overview = _load_batch_overview(batch_dir)
    if not batch_overview:
        return None

    src = str(batch_overview.get("source_file") or "").replace("\\", "/")
    if stem not in src and Path(src).stem != stem:
        return None

    batch_by_id: dict[str, dict[str, Any]] = {}
    for item in batch_overview.get("cases") or []:
        if isinstance(item, dict) and item.get("case_id"):
            batch_by_id[str(item["case_id"])] = item

    matched = []
    for item in plan_items:
        cid = str(item.get("case_id") or "")
        if cid and cid in batch_by_id:
            matched.append(batch_by_id[cid])
    if not matched:
        total = int(batch_overview.get("total_cases") or 0)
        passed = int(batch_overview.get("passed_cases") or 0)
        if total <= 0:
            return None
        return {
            "passed": passed,
            "total": total,
            "success_rate": str(batch_overview.get("success_rate") or ""),
            "report_html": report_html,
        }

    passed = sum(1 for r in matched if r.get("passed"))
    total = len(matched)
    return {
        "passed": passed,
        "total": total,
        "success_rate": f"{(passed / total * 100):.0f}%" if total else "0%",
        "report_html": report_html,
    }


def _build_case_file_summaries(
    project_dir: Path,
    case_stems: list[str],
    plan_names: list[str],
    batches_by_stem: dict[str, Path],
    report_html_by_stem: dict[str, str],
) -> list[dict[str, Any]]:
    """每个 cases/*.md 文件一条：测什么功能、是否有规划、是否已验收."""
    plan_stems = {name.replace("_actions.json", "") for name in plan_names}
    cases_root = Path(project_dir) / CASES_DIR_NAME
    summaries: list[dict[str, Any]] = []

    for stem in case_stems:
        plan_path = action_plans_dir(project_dir) / f"{stem}_actions.json"
        plan_items: list[dict[str, Any]] = []
        if plan_path.is_file():
            try:
                data = json.loads(plan_path.read_text(encoding="utf-8"))
                raw = data.get("cases") if isinstance(data, dict) else []
                plan_items = [x for x in (raw or []) if isinstance(x, dict)]
            except Exception as exc:
                logger.warning("动作规划解析失败 %s: %s", plan_path, exc)

        entry: dict[str, Any] = {
            "file": stem,
            "description": _describe_case_file(stem, plan_items, cases_root / f"{stem}.md"),
            "has_action_plan": stem in plan_stems,
            "case_count": len(plan_items) if plan_items else None,
        }
        report_html = report_html_by_stem.get(stem, "")
        if report_html:
            entry["report_html"] = report_html
        verification = _verification_for_file(
            stem,
            plan_items,
            batches_by_stem.get(stem),
            report_html=report_html,
        )
        if verification:
            entry["verification"] = verification
        summaries.append(entry)
    return summaries


def promote_planned_actions_from_batch(
    project_dir: Path,
    batch_dir: Path,
    case_ids: Optional[list[str]] = None,
) -> list[str]:
    """将批次输出中的 planned_actions.json 晋升到 action_plans/."""
    promoted: list[str] = []
    batch = Path(batch_dir)
    if not batch.is_dir():
        return promoted
    targets = case_ids or [d.name for d in batch.iterdir() if d.is_dir()]
    for case_id in targets:
        src = planned_actions_file(batch / case_id)
        if src is None or not src.is_file():
            continue
        try:
            actions = json.loads(src.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("跳过晋升 %s: %s", src, exc)
            continue
        if not isinstance(actions, list) or not actions:
            continue
        save_planned_actions(project_dir, case_id, actions)
        promoted.append(case_id)
    return promoted


def _copy_cases(project_dir: Path, dest: Path, case_ids: list[str]) -> list[str]:
    copied: list[str] = []
    src_root = Path(project_dir) / CASES_DIR_NAME
    dest_root = dest / CASES_DIR_NAME
    dest_root.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        src = src_root / f"{case_id}.md"
        if not src.is_file():
            logger.warning("用例不存在: %s", src)
            continue
        shutil.copy2(src, dest_root / src.name)
        copied.append(case_id)
    return copied


def _copy_action_plans(project_dir: Path, dest: Path, case_ids: list[str]) -> list[str]:
    copied: list[str] = []
    dest_root = dest / plan_dir_name(project_dir)
    dest_root.mkdir(parents=True, exist_ok=True)
    for stem in case_ids:
        name = f"{stem}_actions.json"
        src = action_plans_dir(project_dir) / name
        if not src.is_file():
            continue
        shutil.copy2(src, dest_root / name)
        copied.append(name)
    return copied


def _copy_accel_snapshot(
    system_accel_dir: Path,
    dest_accel_dir: Path,
    policy: dict[str, bool],
) -> dict[str, Any]:
    """按 config delivery.accel 复制加速记忆快照到交付包."""
    src = Path(system_accel_dir)
    dest = Path(dest_accel_dir)
    dest.mkdir(parents=True, exist_ok=True)

    l1_name, l2_name, l4_name = accel_subdir_names(src)
    includes: list[str] = []
    excludes: list[str] = []
    stats: dict[str, Any] = {"l1_files": 0, "l2_route_files": 0, "l4_entries": 0}

    if policy.get("include_l1"):
        l1_src = l1_session_dir(src)
        l1_dest = dest / l1_name
        if l1_src.is_dir():
            if l1_dest.exists():
                shutil.rmtree(l1_dest)
            shutil.copytree(l1_src, l1_dest)
            stats["l1_files"] = sum(1 for f in l1_dest.rglob("*.json") if f.is_file())
        if stats["l1_files"] or l1_dest.exists():
            includes.append(l1_name)
    else:
        excludes.append(l1_name)
        l1_dest = dest / l1_name
        if l1_dest.exists():
            shutil.rmtree(l1_dest)

    if policy.get("include_l2", True):
        l2_src = l2_pages_dir(src)
        l2_dest = dest / l2_name
        if l2_src.is_dir():
            l2_dest.mkdir(parents=True, exist_ok=True)
            for f in sorted(l2_src.iterdir()):
                if not f.is_file() or f.suffix != ".json":
                    continue
                if f.name in _L2_SKIP_NAMES or any(f.name.endswith(s) for s in _L2_SKIP_SUFFIXES):
                    continue
                shutil.copy2(f, l2_dest / f.name)
                stats["l2_route_files"] += 1
        if stats["l2_route_files"] or l2_dest.exists():
            includes.append(l2_name)
    else:
        excludes.append(l2_name)
        l2_dest = dest / l2_name
        if l2_dest.exists():
            shutil.rmtree(l2_dest)

    if policy.get("include_l4", True):
        l4_src = l4_structure_dir(src)
        l4_dest = dest / l4_name
        if l4_src.is_dir():
            l4_dest.mkdir(parents=True, exist_ok=True)
            for f in l4_src.iterdir():
                if f.is_file() and f.suffix == ".json":
                    shutil.copy2(f, l4_dest / f.name)
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            stats["l4_entries"] = max(
                                stats["l4_entries"], len(data.get("pages", data)),
                            )
                    except Exception:
                        pass
        if stats["l4_entries"] or l4_dest.exists():
            includes.append(l4_name)
    else:
        excludes.append(l4_name)
        l4_dest = dest / l4_name
        if l4_dest.exists():
            shutil.rmtree(l4_dest)

    return {"includes": includes, "excludes": excludes, **stats}


def _copy_case_screenshots_for_batch(batch: Path, reports_dir: Path, overview: dict[str, Any]) -> None:
    """复制批次报告中引用的失败截图，使 delivery/reports/*.html 内链接可打开."""
    from ...ports.report import copy_batch_failure_screenshots

    copy_batch_failure_screenshots(batch, reports_dir, overview)


def _copy_reports(dest: Path, batches_by_stem: dict[str, Path]) -> list[dict[str, Any]]:
    """复制各用例文件的验收 HTML 到 reports/（与 cases/、actions/ 并列）。"""
    reports_dir = dest / PROJECT_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []

    for stem in sorted(batches_by_stem):
        batch = batches_by_stem[stem]
        src_html = batch / "report_overview.html"
        if not src_html.is_file():
            continue
        report_name = f"{stem}.html"
        report_rel = f"{PROJECT_REPORTS_DIR}/{report_name}"
        shutil.copy2(src_html, reports_dir / report_name)

        data = _load_batch_overview(batch)
        if data:
            _copy_case_screenshots_for_batch(batch, reports_dir, data)
        entry: dict[str, Any] = {
            "file": stem,
            "report_html": report_rel,
        }
        if data:
            entry.update({
                "total_cases": data.get("total_cases", 0),
                "passed_cases": data.get("passed_cases", 0),
                "failed_cases": data.get("failed_cases", 0),
                "success_rate": data.get("success_rate", ""),
                "execution_time": data.get("execution_time", ""),
            })
        entries.append(entry)
    return entries


def export_delivery_package(
    project_dir: Path,
    system_dir: Path,
    version: str,
    *,
    project_root: Path | None = None,
    case_ids: Optional[list[str]] = None,
    batch_dir: Optional[Path] = None,
    use_batch: bool = True,
    promote_plans: bool = False,
    notes: str = "",
    config: dict[str, Any] | None = None,
) -> Path:
    """导出交付包到 business/<方向>/<业务>/<项目>/delivery/<version>/."""
    project_dir = Path(project_dir).resolve()
    system_dir = Path(system_dir).resolve()
    root = Path(project_root).resolve() if project_root else project_dir.parent.parent.parent

    resolved_batch: Path | None = None
    if use_batch:
        resolved_batch = find_batch_dir(root, project_dir, explicit=batch_dir)

    out = delivery_dir(project_dir, version)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    if promote_plans and resolved_batch is not None:
        promote_planned_actions_from_batch(project_dir, resolved_batch, case_ids)

    ids = case_ids or list_case_ids(project_dir)
    copied_cases = _copy_cases(project_dir, out, ids)
    copied_plans = _copy_action_plans(project_dir, out, copied_cases)

    accel_src = accel_memory_path(system_dir)
    accel_policy = delivery_accel_policy(config)
    _copy_accel_snapshot(accel_src, out / SELECTORS_DIR, accel_policy)

    batches_by_stem = (
        find_report_batches(root, project_dir, copied_cases, explicit=resolved_batch)
        if use_batch
        else {}
    )
    reports = _copy_reports(out, batches_by_stem)
    report_html_by_stem = {item["file"]: str(item["report_html"]) for item in reports}

    direction = find_direction_dir(system_dir)
    base_url, api_base_url, roles = resolve_project_runtime(
        system_dir, project_dir, direction_dir=direction,
    )
    case_files = _build_case_file_summaries(
        project_dir,
        copied_cases,
        copied_plans,
        batches_by_stem,
        report_html_by_stem,
    )

    manifest: dict[str, Any] = {
        "version": version,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project": {
            "direction": direction.name if direction else "",
            "system": system_dir.name,
            "name": project_dir.name,
        },
        "environment": {
            "base_url": base_url,
            "roles": _roles_for_manifest(roles),
        },
        "reports": reports,
        "case_files": case_files,
    }
    if notes.strip():
        manifest["notes"] = notes.strip()
    (out / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("Delivery package exported: %s (%d cases)", out, len(copied_cases))
    return out
