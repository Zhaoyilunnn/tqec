"""Public exports, loaded when requested."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._version import __version__ as __version__
    from .compile import compile_block_graph as compile_block_graph
    from .computation.block_graph import BlockGraph as BlockGraph
    from .utils import Basis as Basis
    from .utils import NoiseModel as NoiseModel


_EXPORTS = {
    "__version__": ("._version", "__version__"),
    "compile_block_graph": (".compile", "compile_block_graph"),
    "BlockGraph": (".computation.block_graph", "BlockGraph"),
    "Basis": (".utils", "Basis"),
    "NoiseModel": (".utils", "NoiseModel"),
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
