"""业务目录加载器 — 从用例路径发现 domain_knowledge.md + project.env.

目录层级（新）:
  business/<方向>/<业务>/<项目>/cases/*.md
旧二层结构仍兼容:
  business/<业务>/<项目>/cases/*.md
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Optional

from ...foundation.layout import (
    CASES_DIR,
    DOMAIN_KNOWLEDGE_FILE,
    LEGACY_PROJECT_CONFIG_FILE,
    LEGACY_PROJECT_ENV_FILE,
    PROJECT_CONFIG_FILE,
    PROJECT_ENV_FILE,
    domain_knowledge_path,
    find_direction_dir,
    first_existing,
)
from .accel_store import business_accel_dir
from .env import load_merged_project_env, resolve_project_runtime, substitute_env_placeholders


class BusinessLoader:
    def __init__(self) -> None:
        # 业务方向，如 business/tiku/；旧结构为 None
        self.direction_dir: Path | None = None
        # 业务（系统）目录，如 business/tiku/tiku_video/；含 domain_knowledge.md
        self.system_dir: Path | None = None
        self.business_dir: Path | None = None  # 与 system_dir 同义，保留兼容
        # 项目目录，如 .../大学增加前审/
        self.project_dir: Path | None = None
        self.knowledge: dict[str, Any] = {}
        self.project_config: dict[str, Any] = {}
        self._base_url: str = ""
        self._api_base_url: str = ""
        self._roles: dict[str, dict[str, str]] = {}
        self._extra_env_file: Path | None = None

    def discover(
        self,
        case_file: str | Path,
        *,
        env_file: str | Path | None = None,
    ) -> bool:
        """从用例路径向上扫描业务方向、业务系统目录与项目目录."""
        if env_file:
            self._extra_env_file = Path(env_file).resolve()

        p = Path(case_file).resolve()
        system_dir = _find_system_dir(p)
        if not system_dir:
            return False

        self.system_dir = system_dir
        self.business_dir = system_dir
        self.direction_dir = find_direction_dir(system_dir)

        kb_file = domain_knowledge_path(system_dir)
        raw_knowledge: dict[str, Any] = {}
        if kb_file is not None:
            raw_knowledge = _parse_kb(kb_file.read_text(encoding="utf-8"))

        self.project_dir = _find_project_dir(p, system_dir)
        yaml_cfg: dict[str, Any] = {}
        if self.project_dir is not None:
            yaml_path = first_existing(
                self.project_dir, PROJECT_CONFIG_FILE, LEGACY_PROJECT_CONFIG_FILE
            )
            if yaml_path is not None and yaml_path.is_file():
                yaml_cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                self.project_config = yaml_cfg

        merged_env = load_merged_project_env(
            self.system_dir,
            self.project_dir,
            direction_dir=self.direction_dir,
            extra_env_file=self._extra_env_file,
        )
        self.knowledge = substitute_env_placeholders(raw_knowledge, merged_env)

        self._base_url, self._api_base_url, self._roles = resolve_project_runtime(
            self.system_dir,
            self.project_dir,
            direction_dir=self.direction_dir,
            extra_env_file=self._extra_env_file,
            yaml_fallback=yaml_cfg,
        )
        return bool(self.knowledge or self._base_url or self._roles)

    @property
    def accel_dir(self) -> Path | None:
        if self.system_dir is None:
            return None
        return business_accel_dir(self.system_dir)

    def get_knowledge(self) -> dict[str, Any]:
        return self.knowledge

    def get_base_url(self) -> str:
        return self._base_url

    def get_api_base_url(self) -> str:
        return self._api_base_url

    def get_login_page(self) -> dict[str, Any]:
        return self.knowledge.get("login_page", {})

    def get_roles(self) -> dict[str, dict[str, str]]:
        return self._roles

    def get_apis(self) -> dict[str, Any]:
        return self.knowledge.get("apis", {})

    def get_enums(self) -> dict[str, Any]:
        return self.knowledge.get("enums", {})

    def get_resources(self) -> dict[str, str]:
        return self.knowledge.get("resources", {})

    def display_path(self) -> str:
        """控制台展示用：方向 / 业务 / 项目."""
        parts: list[str] = []
        if self.direction_dir is not None:
            parts.append(f"方向: {self.direction_dir.name}")
        if self.system_dir is not None:
            parts.append(f"业务: {self.system_dir.name}")
        if self.project_dir is not None:
            parts.append(f"项目: {self.project_dir.name}")
        return " | ".join(parts) if parts else "-"

    def build_system_profile(self):
        from ...foundation.profile import ApiTemplate, SystemProfile

        apis = {}
        for name, cfg in self.get_apis().items():
            if not isinstance(cfg, dict):
                continue
            apis[name] = ApiTemplate(
                method=str(cfg.get("method", "GET")).upper(),
                url=str(cfg.get("url", "")),
                type=str(cfg.get("type", "http")),
                base_url=str(cfg.get("base_url", "") or ""),
                body=cfg.get("body"),
                params=cfg.get("params"),
                returns=cfg.get("returns", []),
                keywords=cfg.get("keywords", []),
                retry=cfg.get("retry", {}),
                param_rules=cfg.get("param_rules", []),
            )
        return SystemProfile(
            name=self.system_dir.name if self.system_dir else "default",
            base_url=self.get_base_url(),
            api_base_url=self.get_api_base_url(),
            database=self.get_knowledge().get("database", {}),
            apis=apis,
            enums=self.get_enums() or {},
            resources=self.get_resources() or {},
        )


def _find_system_dir(case_path: Path) -> Path | None:
    """向上查找含 domain_knowledge.md 的业务（系统）目录."""
    parent = case_path.parent if case_path.is_file() else case_path
    while True:
        if domain_knowledge_path(parent) is not None:
            return parent
        if parent == parent.parent:
            return None
        parent = parent.parent


def _find_project_dir(case_path: Path, system_dir: Path) -> Path | None:
    p = case_path.resolve()
    if p.suffix.lower() == ".md" and p.parent.name == CASES_DIR:
        return p.parent.parent
    cur = p.parent if p.is_file() else p
    while cur != system_dir and cur != cur.parent:
        if first_existing(
            cur, PROJECT_ENV_FILE, LEGACY_PROJECT_ENV_FILE, ".env", ".env.local"
        ) is not None:
            return cur
        if first_existing(cur, PROJECT_CONFIG_FILE, LEGACY_PROJECT_CONFIG_FILE) is not None:
            return cur
        if (cur / CASES_DIR).is_dir():
            return cur
        cur = cur.parent
    return None


def _parse_kb(text: str) -> dict[str, Any]:
    t = text.lstrip()
    if not t.startswith("---"):
        return {}
    parts = t.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1].strip()) or {}
    except Exception:
        return {}
