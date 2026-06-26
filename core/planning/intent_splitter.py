"""兼容层 → core.pipeline.planning.intent_splitter"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.pipeline.planning.intent_splitter")
_sys.modules[__name__] = _target
