"""兼容层 → core.runtime.execution.submit_post_verify"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.runtime.execution.submit_post_verify")
_sys.modules[__name__] = _target
