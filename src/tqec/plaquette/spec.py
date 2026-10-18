"""Immutable physical construction parameters, independent of circuit implementations."""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass

from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict


@dataclass(frozen=True)
class RPNGPlaquetteSpec:
    """Describe a square plaquette using the standard RPNG construction.

    Measurement timing is a construction parameter. Circuit transformations and
    their resulting footprints belong to the lowering implementation.
    """

    description: RPNGDescription
    measurement_schedule: int = MEASUREMENT_SCHEDULE

    @property
    def num_moments(self) -> int:
        """Return the timing extent of the standard RPNG construction."""
        desc = self.description
        if desc.ancilla.g is not None or any(c.g is not None for c in desc.corners):
            return self.measurement_schedule + 1
        gates = [c.n for c in desc.corners if c.p is not None and c.n is not None]
        return max(gates, default=0) + 1


PlaquetteSpec = RPNGPlaquetteSpec


@dataclass(frozen=True)
class PlaquetteSpecs:
    """Associate nonzero template indices with immutable construction descriptions."""

    collection: FrozenDefaultDict[int, PlaquetteSpec]

    def __post_init__(self) -> None:
        if 0 in self.collection:
            raise TQECError("Index 0 is reserved for no plaquette.")

    def __getitem__(self, index: int) -> PlaquetteSpec:
        return self.collection[index]

    def with_updated_specs(self, updates: Mapping[int, PlaquetteSpec]) -> "PlaquetteSpecs":
        """Return a collection with the supplied indices replaced."""
        return PlaquetteSpecs(self.collection | updates)

    def without_specs(self, indices: Collection[int]) -> "PlaquetteSpecs":
        """Return a collection without the supplied explicit indices."""
        return PlaquetteSpecs(
            FrozenDefaultDict(
                {k: v for k, v in self.collection.items() if k not in indices},
                default_value=self.collection.default_value,
            )
        )

    def map_indices(self, mapping: Callable[[int], int]) -> "PlaquetteSpecs":
        """Return a collection with remapped indices and the same default."""
        return PlaquetteSpecs(self.collection.map_keys(mapping))

    def without_plaquettes(self, indices: Collection[int]) -> "PlaquetteSpecs":
        """Implement the shared template collection trimming operation."""
        return self.without_specs(indices)

    def with_updated_plaquettes(self, updates: Mapping[int, PlaquetteSpec]) -> "PlaquetteSpecs":
        """Implement the shared template collection replacement operation."""
        return self.with_updated_specs(updates)
