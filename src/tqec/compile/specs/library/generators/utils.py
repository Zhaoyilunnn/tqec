"""Pure helpers for construction generators."""

from typing import Literal

from tqec.compile.specs.base import CubeSpec
from tqec.utils.enums import Basis


def should_reset_spatial_arm_data(cube: CubeSpec | None, reset: Basis | None) -> bool:
    """Return whether a spatial-arm plaquette should reset the neighboring data qubits."""
    return cube is not None and reset is not None and not cube.has_bottom_temporal_pipe


def should_measure_spatial_arm_data(cube: CubeSpec | None, measurement: Basis | None) -> bool:
    """Return whether a spatial-arm plaquette should measure the neighboring data qubits."""
    return cube is not None and measurement is not None and not cube.has_top_temporal_pipe


def get_reset_measurement_indices_for_spatial_arms(
    default_indices: tuple[Literal[0, 1, 2, 3], ...],
    cube: CubeSpec | None,
    reset: Basis | None,
    measurement: Basis | None,
) -> tuple[tuple[Literal[0, 1, 2, 3], ...], tuple[Literal[0, 1, 2, 3], ...]]:
    """Get the reset and measurement indices for plaquettes in spatial arms.

    If the neighboring cube applies resets or measurements at the same layer,
    the plaquette in a spatial arm should also apply the reset or measurement
    on corresponding data qubits.

    # See: https://github.com/tqec/tqec/issues/1062

    Args:
        default_indices: the default data qubit indices for the plaquette in
            the spatial arm to apply resets or measurements.
        cube: the neighboring cube to check for resets or measurements.
        reset: the reset basis. ``None`` if no reset is applied.
        measurement: the measurement basis. ``None`` if no measurement is applied.

    Returns:
        the data-qubit indices to reset and the data-qubit indices to measure.

    """
    reset_indices = (0, 1, 2, 3) if should_reset_spatial_arm_data(cube, reset) else default_indices
    measured_indices = (
        (0, 1, 2, 3) if should_measure_spatial_arm_data(cube, measurement) else default_indices
    )
    return reset_indices, measured_indices
