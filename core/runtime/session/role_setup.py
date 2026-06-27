"""角色登录后初始化 — 注入 Cookie、处理 403 引导页等."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def apply_role_setup(
    page: Any,
    role: str,
    knowledge: dict[str, Any] | None,
    base_url: str = "",
    *,
    console: Any | None = None,
) -> None:
    """按 domain_knowledge.role_setup[role] 执行登录后初始化."""
    setups = (knowledge or {}).get("role_setup") or {}
    cfg = setups.get(role)
    if not isinstance(cfg, dict):
        return

    host = _host_from_url(base_url)

    cookies = cfg.get("cookies") or []
    if cookies:
        cookie_list = []
        for item in cookies:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            cookie_list.append(
                {
                    "name": str(item["name"]),
                    "value": str(item.get("value", "")),
                    "domain": str(item.get("domain") or host),
                    "path": str(item.get("path") or "/"),
                }
            )
        if cookie_list:
            page.context.add_cookies(cookie_list)
            _log(console, f"  [dim]角色 {role}: 已注入 Cookie {', '.join(c['name'] for c in cookie_list)}[/dim]")

    for step in cfg.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if "goto" in step:
            url = _resolve_url(str(step["goto"]), base_url)
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            _log(console, f"  [dim]角色 {role}: 访问 {url[:80]}[/dim]")
        elif "click" in step:
            label = str(step["click"])
            if not _click_label(page, label):
                _log(console, f"  [yellow]角色 {role}: 未找到可点击项「{label}」(继续)[/yellow]")
            else:
                _log(console, f"  [dim]角色 {role}: 点击「{label}」[/dim]")
        elif step.get("reload"):
            page.reload(wait_until="domcontentloaded", timeout=15000)
            _log(console, f"  [dim]角色 {role}: 已刷新页面[/dim]")

    try:
        from ..execution.popup_recovery import wait_and_dismiss_blocking_dialog

        wait_and_dismiss_blocking_dialog(page)
        _log(console, f"  [dim]角色 {role}: 已尝试关闭红线阻断弹窗[/dim]")
    except Exception:
        pass


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


def _resolve_url(path_or_url: str, base_url: str) -> str:
    path_or_url = (path_or_url or "").strip()
    if path_or_url.startswith("http"):
        return path_or_url
    base = (base_url or "").rstrip("/")
    if not path_or_url.startswith("/"):
        path_or_url = "/" + path_or_url
    if not base:
        return path_or_url
    parsed = urlparse(base)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else base
    # base_url 已含 /video 时避免 /video/video/...
    if origin.endswith(path_or_url.rstrip("/")):
        return origin
    if path_or_url in base:
        return base
    return origin + path_or_url


def _click_label(page: Any, label: str) -> bool:
    for factory in (
        lambda: page.get_by_role("button", name=label, exact=False).first,
        lambda: page.get_by_role("link", name=label, exact=False).first,
        lambda: page.get_by_text(label, exact=False).first,
    ):
        try:
            loc = factory()
            loc.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


def _log(console: Any | None, message: str) -> None:
    if console is not None:
        console.print(message)
