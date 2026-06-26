"""兼容层 → core.runtime.execution.post_submit_eval"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.execution.post_submit_eval")
_sys.modules[__name__] = _target
