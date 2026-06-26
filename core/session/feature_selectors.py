"""兼容层 → core.runtime.session.feature_selectors"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.session.feature_selectors")
_sys.modules[__name__] = _target
