"""项目级 .env 解析：BASE_URL + 多角色账号（ROLE_<名>_<字段> 或 <名>_<字段>）."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ...foundation.layout import (
    BUSINESS_ENV_FILE,
    DIRECTION_ENV_FILE,
    LEGACY_BUSINESS_ENV_FILE,
    LEGACY_PROJECT_ENV_FILE,
    PROJECT_ENV_FILE,
    SYSTEM_ENV_FILE,
    first_existing,
)

_ROLE_FIELD_RE = re.compile(
    r"^ROLE_(?P<role>.+)_(?P<field>USERNAME|PASSWORD|VERIFY_CODE)$",
    re.IGNORECASE,
)
_PLAIN_ROLE_FIELD_RE = re.compile(
    r"^(?P<role>.+)_(?P<field>USERNAME|PASSWORD|VERIFY_CODE)$",
    re.IGNORECASE,
)
_RESERVED_ENV_PREFIXES = ("BASE_", "ENV", "UI_TEST_", "ROLE_")


def load_dotenv_file(path: Path) -> dict[str, str]:
    """解析 KEY=VALUE 文本（不依赖 python-dotenv）."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def merge_env_layers(*layers: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for layer in layers:
        for k, v in layer.items():
            if v is not None and str(v).strip() != "":
                merged[k] = str(v).strip()
    return merged


def os_env_project_keys() -> dict[str, str]:
    """进程环境变量中与本框架相关的键."""
    prefixes = ("BASE_", "ROLE_", "ENV", "UI_TEST_", "VPSAPI_", "VPSCORE_", "API_")
    return {
        k: v
        for k, v in os.environ.items()
        if k.startswith(prefixes) and v.strip()
    }


def _role_field_dest(field: str) -> str:
    f = field.lower()
    if f == "verify_code":
        return "verify_code"
    if f == "username":
        return "username"
    return "password"


def parse_roles_from_env(env: dict[str, str]) -> dict[str, dict[str, str]]:
    """ROLE_admin_USERNAME 或 admin_USERNAME → roles['admin']['username']."""
    roles: dict[str, dict[str, str]] = {}
    for key, val in env.items():
        m = _ROLE_FIELD_RE.match(key)
        if not m:
            if any(key.upper().startswith(p) for p in _RESERVED_ENV_PREFIXES):
                continue
            m = _PLAIN_ROLE_FIELD_RE.match(key)
            if not m:
                continue
        role = m.group("role")
        roles.setdefault(role, {})[_role_field_dest(m.group("field"))] = val
    return roles


def _load_project_env_files(project_dir: Path) -> list[dict[str, str]]:
    layers: list[dict[str, str]] = []
    for name in (PROJECT_ENV_FILE, LEGACY_PROJECT_ENV_FILE, ".env", ".env.local"):
        p = project_dir / name
        if p.is_file():
            layers.append(load_dotenv_file(p))
    return layers


def _load_direction_env_files(direction_dir: Path) -> list[dict[str, str]]:
    layers: list[dict[str, str]] = []
    for name in (DIRECTION_ENV_FILE, SYSTEM_ENV_FILE, BUSINESS_ENV_FILE, LEGACY_BUSINESS_ENV_FILE):
        p = direction_dir / name
        if p.is_file():
            layers.append(load_dotenv_file(p))
    return layers


_ENV_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def substitute_env_placeholders(obj: Any, env: dict[str, str]) -> Any:
    r"""递归替换字符串中的 ${ENV_KEY}；仅当 key 存在于 env 时替换，保留运行时 ${tid} 等."""
    if isinstance(obj, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return env[key] if key in env else match.group(0)

        return _ENV_PLACEHOLDER_RE.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: substitute_env_placeholders(v, env) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_env_placeholders(v, env) for v in obj]
    return obj


def load_merged_project_env(
    system_dir: Path | None,
    project_dir: Path | None,
    *,
    direction_dir: Path | None = None,
    extra_env_file: Path | None = None,
) -> dict[str, str]:
    """合并 direction / business / project .env 与进程环境（全量键，供知识库变量替换）."""
    layers: list[dict[str, str]] = []
    if direction_dir is not None:
        layers.extend(_load_direction_env_files(direction_dir))
    if system_dir is not None:
        for name in (SYSTEM_ENV_FILE, BUSINESS_ENV_FILE, LEGACY_BUSINESS_ENV_FILE):
            p = system_dir / name
            if p.is_file():
                layers.append(load_dotenv_file(p))
    if project_dir is not None:
        layers.extend(_load_project_env_files(project_dir))
    if extra_env_file is not None:
        layers.append(load_dotenv_file(extra_env_file))
    layers.append(os_env_project_keys())
    return merge_env_layers(*layers)


def runtime_from_env(
    env: dict[str, str],
    yaml_fallback: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, dict[str, str]]]:
    """从已合并 env 解析 base_url / api_base_url / roles."""
    base_url = env.get("BASE_URL", "")
    api_base_url = env.get("VPSAPI_BASE_URL") or env.get("API_BASE_URL", "")
    roles = parse_roles_from_env(env)

    yaml_fallback = yaml_fallback or {}
    if not base_url:
        base_url = str(yaml_fallback.get("base_url") or "").strip()
    if not api_base_url:
        api_base_url = str(yaml_fallback.get("api_base_url") or "").strip()
    if not api_base_url and base_url:
        api_base_url = origin_from_url(base_url)
    if not roles:
        raw_roles = yaml_fallback.get("roles") or {}
        if isinstance(raw_roles, dict):
            roles = {
                str(k): {str(fk): str(fv) for fk, fv in (v or {}).items()}
                for k, v in raw_roles.items()
                if isinstance(v, dict)
            }
    return base_url, api_base_url, roles


def origin_from_url(url: str) -> str:
    """从完整 URL 提取 scheme://host（用于 API / Cookie 域名）."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw.rstrip("/")


def resolve_project_runtime(
    system_dir: Path | None,
    project_dir: Path | None,
    *,
    direction_dir: Path | None = None,
    extra_env_file: Path | None = None,
    yaml_fallback: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, dict[str, str]]]:
    """合并 direction / business / project .env 与进程环境；yaml 仅兜底.

    返回 (base_url, api_base_url, roles).
    api_base_url 优先级: VPSAPI_BASE_URL > API_BASE_URL > yaml > 从 BASE_URL 推导 origin.
    """
    env = load_merged_project_env(
        system_dir,
        project_dir,
        direction_dir=direction_dir,
        extra_env_file=extra_env_file,
    )
    return runtime_from_env(env, yaml_fallback)
