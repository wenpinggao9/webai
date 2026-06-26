"""兼容层 → core.runtime.execution.recovery_exec"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.execution.recovery_exec")
_sys.modules[__name__] = _target
