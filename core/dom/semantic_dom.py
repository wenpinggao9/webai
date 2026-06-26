"""兼容层 → core.understanding.dom.semantic_dom"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.understanding.dom.semantic_dom")
_sys.modules[__name__] = _target
