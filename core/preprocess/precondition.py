"""兼容层 → core.pipeline.preprocess.precondition"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.pipeline.preprocess.precondition")
_sys.modules[__name__] = _target
