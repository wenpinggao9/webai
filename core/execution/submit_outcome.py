"""兼容层 → core.runtime.execution.submit_outcome"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.execution.submit_outcome")
_sys.modules[__name__] = _target
