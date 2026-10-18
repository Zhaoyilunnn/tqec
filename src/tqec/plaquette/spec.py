"""Immutable physical construction parameters, independent of circuit implementations."""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace

from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.utils.enums import Basis, Orientation
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
    compiled: bool = False

    @property
    def num_moments(self) -> int:
        """Return the timing extent of the standard RPNG construction."""
        desc = self.description
        if desc.ancilla.g is not None or any(c.g is not None for c in desc.corners):
            return self.measurement_schedule + 1
        gates = [c.n for c in desc.corners if c.p is not None and c.n is not None]
        return max(gates, default=0) + 1


@dataclass(frozen=True)
class DataQubitOperations:
    """Reset and measurement applied to data qubits of one plaquette."""

    reset: Basis | None = None
    measurement: Basis | None = None


@dataclass(frozen=True)
class ExtendedPlaquetteDataQubitsOperations:
    """Independent data operations for the first and second extended halves."""

    first: DataQubitOperations = DataQubitOperations()
    second: DataQubitOperations = DataQubitOperations()


@dataclass(frozen=True)
class ExtendedPlaquetteSpec:
    """Select one shaped half of the existing extended stabilizer construction."""

    description: RPNGDescription
    reset: Basis | None
    measurement: Basis | None
    is_reversed: bool
    orientation: Orientation
    data_operations: ExtendedPlaquetteDataQubitsOperations
    shape: str
    second: bool

    @property
    def num_moments(self) -> int:
        """Return the extent including retained empty trailing moments."""
        operations = self.data_operations.second if self.second else self.data_operations.first
        if (
            self.is_reversed != self.second
            or self.measurement is not None
            or operations.measurement is not None
        ):
            return 8
        return 6


@dataclass(frozen=True)
class RealignmentPlaquetteSpec:
    """Parameters of the fixed-bulk temporal Hadamard realignment construction."""

    stabilizer_basis: Basis
    z_orientation: Orientation
    mq_reset: Basis
    mq_measurement: Basis
    debug_basis: PauliBasis | None = None
    boundary: PlaquetteOrientation | None = None

    def project_on_boundary(self, orientation: PlaquetteOrientation) -> "RealignmentPlaquetteSpec":
        """Record a boundary projection to apply after materialization."""
        if self.boundary is not None:
            raise TQECError("Repeated realignment boundary projection is not supported.")
        return replace(self, boundary=orientation)

    @property
    def num_moments(self) -> int:
        """Return the extent of the realignment schedule."""
        return 7


PlaquetteSpec = RPNGPlaquetteSpec | ExtendedPlaquetteSpec | RealignmentPlaquetteSpec


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
