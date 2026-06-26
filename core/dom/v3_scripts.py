"""兼容层 → core.understanding.dom.v3_scripts"""
import sys as _sys
from importlib import import_module as _import_module
_target = _import_module("core.understanding.dom.v3_scripts")
_sys.modules[__name__] = _target
