"""工程目录与产物文件名（英文）+ 旧中文路径兼容读取."""
from __future__ import annotations

from pathlib import Path

# ── business/ 业务资产区 ──────────────────────────────────────────
BUSINESS_DIR = "business"
DOMAIN_KNOWLEDGE_FILE = "domain_knowledge.md"
SELECTORS_DIR = "selectors"
ACCEL_MEMORY_DIR = "accel_memory"
BUSINESS_ENV_FILE = "business.env"
DIRECTION_ENV_FILE = "direction.env"
SYSTEM_ENV_FILE = ".env"
PROJECT_ENV_FILE = "project.env"
PROJECT_ENV_EXAMPLE_FILE = "project.env.example"
PROJECT_CONFIG_FILE = "project_config.yaml"
ACTIONS_DIR = "actions"
ACTION_PLANS_DIR = "action_plans"
RESOURCES_DIR = "resources"
TEST_RESOURCES_DIR = "test_resources"
DELIVERY_DIR = "delivery"
ACCEPTANCE_DIR = "acceptance"
CASES_DIR = "cases"
PROJECT_REPORTS_DIR = "reports"
RUN_REF_FILE = "run_ref.json"

# 旧中文名（仅用于发现/迁移）
LEGACY_BUSINESS_DIR = "业务"
LEGACY_DOMAIN_KNOWLEDGE_FILE = "业务知识.md"
LEGACY_ACCEL_MEMORY_DIR = "加速记忆"
LEGACY_BUSINESS_ENV_FILE = "业务.env"
LEGACY_PROJECT_ENV_FILE = "项目.env"
LEGACY_PROJECT_CONFIG_FILE = "项目配置.yaml"
LEGACY_ACTION_PLANS_DIR = "动作规划"
LEGACY_TEST_RESOURCES_DIR = "测试资源"
LEGACY_DELIVERY_DIR = "交付包"
LEGACY_ACCEPTANCE_DIR = "验收"
LEGACY_GLOBAL_ACCEL_DIR = "legacy_accel"

# ── output/ 运行时工作区 ──────────────────────────────────────────
OUTPUT_DIR = "output"
UI_RUNS_DIR = "ui_runs"
PROMPT_REPLAY_DIR = "prompt_replay"

SCREENSHOTS_SUBDIR = "screenshots"
SEMANTIC_DOM_SUBDIR = "semantic_dom"
REPORTS_SUBDIR = "reports"
PARSED_CASE_FILE = "parsed_case.json"
PLANNED_ACTIONS_FILE = "planned_actions.json"
EXECUTION_TRACE_FILE = "execution_trace.json"
OBSERVABILITY_FILE = "observability.json"
PROMPTS_USED_FILE = "prompts_used.md"
LLM_RAW_TXT_FILE = "llm_raw_response.txt"
LLM_RAW_JSON_FILE = "llm_raw_response.json"
EXECUTION_LOG_FILE = "execution_log.json"

LEGACY_OUTPUT_DIR = "输出"
LEGACY_UI_RUNS_DIR = "UI测试"
LEGACY_PROMPT_REPLAY_DIR = "提示词回放"
LEGACY_SCREENSHOTS_SUBDIR = "截图"
LEGACY_SEMANTIC_DOM_SUBDIR = "语义DOM"
LEGACY_REPORTS_SUBDIR = "报告"
LEGACY_PARSED_CASE_FILE = "已解析用例.json"
LEGACY_PLANNED_ACTIONS_FILE = "已规划动作.json"
LEGACY_EXECUTION_TRACE_FILE = "执行追踪.json"
LEGACY_OBSERVABILITY_FILE = "可观测性.json"
LEGACY_PROMPTS_USED_FILE = "使用的模型提示词.md"
LEGACY_LLM_RAW_TXT_FILE = "模型原始响应.txt"
LEGACY_LLM_RAW_JSON_FILE = "模型原始响应.json"
LEGACY_EXECUTION_LOG_FILE = "执行日志.json"
LEGACY_BATCH_REPORT_HTML = "批次报告.html"
LEGACY_RESULTS_SUMMARY_JSON = "结果摘要.json"

BATCH_REPORT_HTML = "batch_report.html"
RESULTS_SUMMARY_JSON = "results_summary.json"


def first_existing(parent: Path, *names: str) -> Path | None:
    for name in names:
        if not name:
            continue
        p = parent / name
        if p.exists():
            return p
    return None


def business_root(project_root: Path) -> Path | None:
    return first_existing(project_root, BUSINESS_DIR, LEGACY_BUSINESS_DIR)


def find_business_root(from_path: Path) -> Path | None:
    """从任意子路径向上定位 business/ 根目录."""
    cur = from_path.resolve()
    if cur.is_file():
        cur = cur.parent
    while cur != cur.parent:
        if cur.name in (BUSINESS_DIR, LEGACY_BUSINESS_DIR):
            return cur
        cur = cur.parent
    return None


def find_direction_dir(business_system_dir: Path) -> Path | None:
    """business/<方向>/<业务>/ → 返回 <方向> 目录；旧二层 business/<业务>/ 返回 None."""
    biz = find_business_root(business_system_dir)
    if biz is None:
        return None
    try:
        rel = business_system_dir.resolve().relative_to(biz.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 2:
        return biz / parts[0]
    return None


def domain_knowledge_path(system_dir: Path) -> Path | None:
    return first_existing(system_dir, DOMAIN_KNOWLEDGE_FILE, LEGACY_DOMAIN_KNOWLEDGE_FILE)


def accel_memory_path(system_dir: Path) -> Path:
    """业务级加速/选择器根目录（selectors/ 或 accel_memory/）."""
    p = first_existing(
        system_dir, SELECTORS_DIR, ACCEL_MEMORY_DIR, LEGACY_ACCEL_MEMORY_DIR
    )
    return p or (system_dir / ACCEL_MEMORY_DIR)


def action_plans_path(project_dir: Path) -> Path:
    p = first_existing(
        project_dir, ACTIONS_DIR, ACTION_PLANS_DIR, LEGACY_ACTION_PLANS_DIR
    )
    return p or (project_dir / ACTION_PLANS_DIR)


def test_resources_path(project_dir: Path) -> Path | None:
    return first_existing(
        project_dir, RESOURCES_DIR, TEST_RESOURCES_DIR, LEGACY_TEST_RESOURCES_DIR
    )


def planned_actions_file(batch_or_case_dir: Path) -> Path | None:
    return first_existing(
        batch_or_case_dir, PLANNED_ACTIONS_FILE, LEGACY_PLANNED_ACTIONS_FILE
    )


def observability_file(case_dir: Path) -> Path | None:
    return first_existing(case_dir, OBSERVABILITY_FILE, LEGACY_OBSERVABILITY_FILE)


def ui_runs_root(project_root: Path) -> Path:
    out = first_existing(project_root, OUTPUT_DIR, LEGACY_OUTPUT_DIR)
    root = out or (project_root / OUTPUT_DIR)
    runs = first_existing(root, UI_RUNS_DIR, LEGACY_UI_RUNS_DIR)
    return runs or (root / UI_RUNS_DIR)
