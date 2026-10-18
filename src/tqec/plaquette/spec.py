"""Immutable physical construction parameters, independent of circuit implementations."""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace

from tqec.circuit.qubit import GridQubit
from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.rpng.rpng import PauliBasis, RPNGDescription
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import PhysicalQubitPosition2D


class _SpecGeometry:
    @property
    def origin(self) -> PhysicalQubitPosition2D:
        """Return the center of the local plaquette coordinates."""
        return PhysicalQubitPosition2D(0, 0)


@dataclass(frozen=True)
class RPNGPlaquetteSpec(_SpecGeometry):
    """Describe a square plaquette using the standard RPNG construction.

    Measurement timing is a construction parameter. Circuit transformations and
    their resulting footprints belong to the lowering implementation.
    """

    description: RPNGDescription
    measurement_schedule: int = MEASUREMENT_SCHEDULE

    @property
    def used_qubits(self) -> frozenset[GridQubit]:
        """Return the qubit map footprint of the standard RPNG construction."""
        square = SquarePlaquetteQubits()
        return frozenset(square.syndrome_qubits) | frozenset(
            square.data_qubits[i]
            for i, corner in enumerate(self.description.corners)
            if corner.r is not None
            or corner.g is not None
            or (corner.p is not None and corner.n is not None)
        )

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
class ExtendedPlaquetteSpec(_SpecGeometry):
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
    def used_qubits(self) -> frozenset[GridQubit]:
        """Return both syndrome qubits and the data corners selected by the shape."""
        side = 1 if self.second else -1
        if self.orientation == Orientation.VERTICAL:
            data = (GridQubit(-1, side), GridQubit(1, side))
            other = (GridQubit(-1, -side), GridQubit(1, -side))
        else:
            data = (GridQubit(side, -1), GridQubit(side, 1))
            other = (GridQubit(-side, -1), GridQubit(-side, 1))
        kept = {
            "bulk": ((0, 1), (0, 1)),
            "bottom_right_triangle": ((1,), (0, 1)),
            "right_half_rectangle": ((1,), (1,)),
            "top_left_triangle": ((0, 1), (0,)),
            "left_half_rectangle": ((0,), (0,)),
            "bottom_left_triangle": ((0,), (0, 1)),
            "top_right_triangle": ((0, 1), (1,)),
        }[self.shape][self.second]
        return frozenset([GridQubit(0, 0), other[self.is_reversed], *(data[i] for i in kept)])

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
class RealignmentPlaquetteSpec(_SpecGeometry):
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
    def used_qubits(self) -> frozenset[GridQubit]:
        """Return the square footprint after any boundary projection."""
        square = SquarePlaquetteQubits()
        data = (
            square.data_qubits
            if self.boundary is None
            else square.get_qubits_on_side(self.boundary.to_plaquette_side())
        )
        return frozenset([*data, *square.syndrome_qubits])

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
