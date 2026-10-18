"""Backend-independent contract for lowering local physical constructions."""

from typing import Protocol, TypeVar

from tqec.plaquette.spec import PlaquetteSpec
from tqec.utils.exceptions import TQECError

PhysicalT_co = TypeVar("PhysicalT_co", covariant=True)


class PlaquetteLowerer(Protocol[PhysicalT_co]):
    """Lower a supported construction without changing the cube and pipe builders.

    Implementations own their physical output type. They must reject unsupported
    specifications explicitly. This local contract does not provide detectors or
    logical observables: an end-to-end backend must implement those separately.
    """

    def materialize_plaquette(self, spec: PlaquetteSpec) -> PhysicalT_co:
        """Realize every operation described by the specification or report unsupported input."""
        ...


class UnsupportedLoweringError(TQECError):
    def __init__(self, backend: str, construction: str, reason: str, location=None) -> None:
        """Report which construction the backend cannot implement and where it occurs."""
        self.backend = backend
        self.construction = construction
        self.reason = reason
        self.location = location
        super().__init__(f"{backend} cannot lower {construction} at {location}: {reason}")
