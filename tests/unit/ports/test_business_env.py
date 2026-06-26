"""Business .env loading and BusinessLoader discovery."""
from __future__ import annotations

from pathlib import Path

from core.foundation.layout import (
    ACCEL_MEMORY_DIR,
    DOMAIN_KNOWLEDGE_FILE,
    PROJECT_ENV_FILE,
    SELECTORS_DIR,
)
from core.business.env import parse_roles_from_env, resolve_project_runtime
from core.business.loader import BusinessLoader, _find_project_dir


def test_parse_roles_from_env():
    env = {
        "BASE_URL": "https://example.com",
        "ROLE_admin_USERNAME": "10086",
        "ROLE_admin_VERIFY_CODE": "111111",
        "ROLE_teacherA_USERNAME": "10010",
        "ROLE_teacherA_VERIFY_CODE": "222222",
    }
    roles = parse_roles_from_env(env)
    assert roles["admin"]["username"] == "10086"
    assert roles["admin"]["verify_code"] == "111111"
    assert roles["teacherA"]["username"] == "10010"


def test_parse_roles_plain_env_keys():
    env = {
        "admin_USERNAME": "18600638431",
        "admin_VERIFY_CODE": "111111",
        "teacherA_USERNAME": "13621190002",
    }
    roles = parse_roles_from_env(env)
    assert roles["admin"]["username"] == "18600638431"
    assert roles["teacherA"]["username"] == "13621190002"


def test_resolve_project_runtime_env_over_yaml(tmp_path):
    proj = tmp_path / "proj"
    (proj / "cases").mkdir(parents=True)
    (proj / PROJECT_ENV_FILE).write_text(
        "BASE_URL=https://from-env.test\nROLE_qa_USERNAME=u1\nROLE_qa_VERIFY_CODE=c1\n",
        encoding="utf-8",
    )
    yaml_cfg = {
        "base_url": "https://from-yaml.test",
        "roles": {"admin": {"username": "old", "verify_code": "000"}},
    }
    base, roles = resolve_project_runtime(None, proj, yaml_fallback=yaml_cfg)
    assert base == "https://from-env.test"
    assert roles["qa"]["username"] == "u1"


def test_business_loader_discover_env(tmp_path):
    system = tmp_path / "vip"
    project = system / "demo"
    cases = project / "cases"
    cases.mkdir(parents=True)
    (system / DOMAIN_KNOWLEDGE_FILE).write_text("---\napi_base_url: https://api.test\n---\n", encoding="utf-8")
    (project / PROJECT_ENV_FILE).write_text(
        "BASE_URL=https://ui.test\nROLE_admin_USERNAME=a\nROLE_admin_VERIFY_CODE=1\n",
        encoding="utf-8",
    )
    case_file = cases / "case1.md"
    case_file.write_text("#### c1\n\n##### 步骤\n\n1. 点击\n", encoding="utf-8")

    biz = BusinessLoader()
    assert biz.discover(case_file)
    assert biz.get_base_url() == "https://ui.test"
    assert biz.get_roles()["admin"]["username"] == "a"
    assert biz.accel_dir == system / ACCEL_MEMORY_DIR


def test_business_loader_discover_selectors_layout(tmp_path):
    system = tmp_path / "tiku"
    project = system / "demo"
    cases = project / "cases"
    (system / SELECTORS_DIR / "cache").mkdir(parents=True)
    cases.mkdir(parents=True)
    (system / DOMAIN_KNOWLEDGE_FILE).write_text("---\napi_base_url: https://api.test\n---\n", encoding="utf-8")
    (project / ".env").write_text(
        "BASE_URL=https://ui.test\nadmin_USERNAME=a\nadmin_VERIFY_CODE=1\n",
        encoding="utf-8",
    )
    case_file = cases / "case1.md"
    case_file.write_text("#### c1\n\n##### 步骤\n\n1. 点击\n", encoding="utf-8")

    biz = BusinessLoader()
    assert biz.discover(case_file)
    assert biz.get_roles()["admin"]["username"] == "a"
    assert biz.accel_dir.name == SELECTORS_DIR


def test_business_loader_discover_four_level_layout(tmp_path):
    """business/<方向>/<业务>/<项目>/cases/ — 新四层结构."""
    direction = tmp_path / "business" / "tiku"
    system = direction / "tiku_video"
    project = system / "demo"
    cases = project / "cases"
    cases.mkdir(parents=True)
    (system / DOMAIN_KNOWLEDGE_FILE).write_text("---\napi_base_url: https://api.test\n---\n", encoding="utf-8")
    (project / PROJECT_ENV_FILE).write_text(
        "BASE_URL=https://ui.test\nadmin_USERNAME=a\nadmin_VERIFY_CODE=1\n",
        encoding="utf-8",
    )
    case_file = cases / "case1.md"
    case_file.write_text("#### c1\n\n##### 步骤\n\n1. 点击\n", encoding="utf-8")

    biz = BusinessLoader()
    assert biz.discover(case_file)
    assert biz.direction_dir == direction
    assert biz.system_dir == system
    assert biz.project_dir == project
    assert "方向: tiku" in biz.display_path()
    assert "业务: tiku_video" in biz.display_path()


def test_resolve_project_runtime_direction_env_overrides(tmp_path):
    direction = tmp_path / "tiku"
    system = direction / "tiku_video"
    project = system / "demo"
    (project / "cases").mkdir(parents=True)
    (direction / ".env").write_text("BASE_URL=https://direction.test\n", encoding="utf-8")
    (system / ".env").write_text("BASE_URL=https://system.test\n", encoding="utf-8")
    base, _ = resolve_project_runtime(system, project, direction_dir=direction)
    assert base == "https://system.test"
    (project / PROJECT_ENV_FILE).write_text("BASE_URL=https://project.test\n", encoding="utf-8")
    base, _ = resolve_project_runtime(system, project, direction_dir=direction)
    assert base == "https://project.test"


def test_find_project_dir_from_cases_path():
    root = Path("/tmp/business/vip/项目/cases/x.md")
    system = Path("/tmp/business/vip")
    found = _find_project_dir(root, system)
    assert found is not None
    assert found.name == "项目"
