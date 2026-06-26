"""兼容层 → core.runtime.session.menu_scanner"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.session.menu_scanner")
_sys.modules[__name__] = _target
