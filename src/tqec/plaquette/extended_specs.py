"""Select extended stabilizer shapes without creating their local circuits."""

from dataclasses import dataclass, fields

from tqec.plaquette.constants import EXTENDED_PLAQUETTE_SCHEDULES
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.spec import ExtendedPlaquetteDataQubitsOperations, ExtendedPlaquetteSpec
from tqec.utils.enums import Basis, Orientation
from tqec.utils.exceptions import TQECError


@dataclass(frozen=True)
class ExtendedSpecPair:
    top: ExtendedPlaquetteSpec
    bottom: ExtendedPlaquetteSpec


@dataclass(frozen=True)
class ExtendedSpecCollection:
    bulk: ExtendedSpecPair
    bottom_right_triangle: ExtendedSpecPair
    right_half_rectangle: ExtendedSpecPair
    top_left_triangle: ExtendedSpecPair
    left_half_rectangle: ExtendedSpecPair
    bottom_left_triangle: ExtendedSpecPair
    top_right_triangle: ExtendedSpecPair

    @classmethod
    def from_description(
        cls,
        description: RPNGDescription,
        reset: Basis | None,
        measurement: Basis | None,
        is_reversed: bool,
        orientation: Orientation = Orientation.VERTICAL,
        data_operations: ExtendedPlaquetteDataQubitsOperations = (
            ExtendedPlaquetteDataQubitsOperations()
        ),
    ) -> "ExtendedSpecCollection":
        """Record the shape selection and independent data operations for each half."""
        if any(c.p is None or c.n is None for c in description.corners):
            raise TQECError("Extended plaquette descriptions must define all four interactions.")
        return cls(
            **{
                field.name: ExtendedSpecPair(
                    *(
                        ExtendedPlaquetteSpec(
                            description,
                            reset,
                            measurement,
                            is_reversed,
                            orientation,
                            data_operations,
                            field.name,
                            second,
                        )
                        for second in (False, True)
                    )
                )
                for field in fields(cls)
            }
        )

    @classmethod
    def from_basis(
        cls,
        basis: Basis,
        reset: Basis | None,
        measurement: Basis | None,
        is_reversed: bool,
        schedule=None,
        orientation: Orientation = Orientation.VERTICAL,
        data_operations: ExtendedPlaquetteDataQubitsOperations = (
            ExtendedPlaquetteDataQubitsOperations()
        ),
    ) -> "ExtendedSpecCollection":
        """Use the same default schedule selection as the concrete construction."""
        if schedule is None:
            schedule = EXTENDED_PLAQUETTE_SCHEDULES[is_reversed]
        return cls.from_description(
            RPNGDescription.from_basis_and_schedule(basis, schedule),
            reset,
            measurement,
            is_reversed,
            orientation,
            data_operations,
        )
