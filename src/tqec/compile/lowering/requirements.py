"""Dependency checks at the physical output boundary."""

from importlib import import_module

from tqec.utils.exceptions import TQECError


def require_stim() -> None:
    """Report missing physical-backend dependencies at the requested output boundary."""
    try:
        import_module("stim")
        import_module("tqecd")
    except ModuleNotFoundError as error:
        if error.name not in {"stim", "tqecd"}:
            raise
        raise TQECError(
            "Stim output requires Stim and tqecd. Install tqec with its declared dependencies."
        ) from error
