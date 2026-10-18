"""Defines a few core data-structures that are independent of other ``tqec`` modules.

The goal of this module is to host data-structures that do not clearly belong to
another existing ``tqec`` sub-module and that also do not import any code from
the other ``tqec`` sub-modules.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import Basis as Basis
    from .enums import Orientation as Orientation
    from .exceptions import TQECError as TQECError
    from .noise_model import NoiseModel as NoiseModel


_EXPORTS = {
    "Basis": (".enums", "Basis"),
    "Orientation": (".enums", "Orientation"),
    "TQECError": (".exceptions", "TQECError"),
    "NoiseModel": (".noise_model", "NoiseModel"),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Load public exports without importing circuit backends eagerly."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module, __name__), attribute)
    globals()[name] = value
    return value


def __dir__():
    """Include lazily loaded public exports in module introspection."""
    return sorted(set(globals()) | set(__all__))
