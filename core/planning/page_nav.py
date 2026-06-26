"""兼容层 → core.pipeline.planning.page_nav"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.pipeline.planning.page_nav")
_sys.modules[__name__] = _target
