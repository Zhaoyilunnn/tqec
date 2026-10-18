"""Map RPNG generator output to construction descriptions without translating it."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec

from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.spec import PlaquetteSpecs, RPNGPlaquetteSpec
from tqec.utils.frozendefaultdict import FrozenDefaultDict

P = ParamSpec("P")


class PlaquetteSpecMapper:
    def __init__(self, measurement_schedule: int = MEASUREMENT_SCHEDULE) -> None:
        """Keep the measurement schedule chosen by the construction convention."""
        self.measurement_schedule = measurement_schedule

    def get_spec(self, description: RPNGDescription) -> RPNGPlaquetteSpec:
        """Preserve the description and timing without constructing a circuit."""
        return RPNGPlaquetteSpec(description, self.measurement_schedule)

    def __call__(
        self, generator: Callable[P, FrozenDefaultDict[int, RPNGDescription]]
    ) -> Callable[P, PlaquetteSpecs]:
        @wraps(generator)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> PlaquetteSpecs:
            return PlaquetteSpecs(generator(*args, **kwargs).map_values(self.get_spec))

        return wrapped
