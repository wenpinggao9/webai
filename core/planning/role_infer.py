"""兼容层 → core.pipeline.planning.role_infer"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.pipeline.planning.role_infer")
_sys.modules[__name__] = _target
