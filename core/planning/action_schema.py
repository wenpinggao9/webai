"""兼容层 → core.pipeline.planning.action_schema"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.pipeline.planning.action_schema")
_sys.modules[__name__] = _target
