"""会话层: 自动登录 (步骤④) + 模块导航 (步骤⑤)."""
from .login import login, url_hints_login
from .navigator import Navigator
from .role_setup import apply_role_setup

__all__ = ["login", "url_hints_login", "Navigator", "apply_role_setup"]
