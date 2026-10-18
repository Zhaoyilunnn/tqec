"""Translate RPNG descriptions into concrete Stim plaquettes."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from types import FunctionType
from typing import Final, ParamSpec, cast

from tqec.compile.lowering.stim.compiler import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.compile.lowering.stim.translator import RPNGTranslator
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict

P = ParamSpec("P")


class PlaquetteMapper:
    def __init__(
        self,
        translator: RPNGTranslator | None = None,
        compiler: PlaquetteCompiler | None = None,
        measurement_schedule: int = MEASUREMENT_SCHEDULE,
    ) -> None:
        """Wrap a translator and a compiler to ease plaquette generation."""
        self._measurement_schedule = measurement_schedule
        self._translator = translator
        self._compiler = IdentityPlaquetteCompiler if compiler is None else compiler

    def get_plaquette(self, description: RPNGDescription) -> Plaquette:
        """Successively call the translator and the compiler to return a plaquette."""
        from tqec.compile.lowering.stim.translator import DefaultRPNGTranslator  # noqa: PLC0415

        if self._translator is None:
            self._translator = DefaultRPNGTranslator(self._measurement_schedule)
        return self._compiler.compile(self._translator.translate(description))

    def __call__(
        self,
        f: Callable[P, FrozenDefaultDict[int, RPNGDescription]],
    ) -> Callable[P, Plaquettes]:
        """Wrap the provided callable ``f`` to automatically get :class:`.Plaquette` instances.

        This method wraps correctly the provided function such that :meth:`get_plaquette` is called
        on each of the returned :class:`.RPNGDescription` instance to get its corresponding
        :class:`.Plaquette`.

        """
        func = cast(FunctionType, f)

        # The wraps decorator make sure that the original function name, module,
        # docstring, ... is correctly transmitted to the wrapper.
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Plaquettes:
            return Plaquettes(f(*args, **kwargs).map_values(self.get_plaquette))

        # Because the function name has to change, we need to explicitly change
        # it here.
        wrapped_func_name = func.__name__
        expected_end = "_rpng_descriptions"
        if not wrapped_func_name.endswith(expected_end):
            raise TQECError(
                f"Cannot wrap function {func.__module__}.{func.__name__}: its name "
                f"does not end with '{expected_end}'."
            )
        wrapped_name = wrapped_func_name[: -len(expected_end)] + "_plaquettes"
        wrapper.__name__ = wrapped_name
        # Return the final function.
        return wrapper


default_plaquette_mapper: Final = PlaquetteMapper()
