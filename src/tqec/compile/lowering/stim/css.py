from typing import Final

from tqec.compile.lowering.stim.compiler import PlaquetteCompiler
from tqec.compile.lowering.stim.passes.controlled_gate_basis import (
    ChangeControlledGateBasisPass,
)
from tqec.compile.lowering.stim.passes.measurement_basis import (
    ChangeMeasurementBasisPass,
)
from tqec.compile.lowering.stim.passes.reset_basis import ChangeResetBasisPass
from tqec.compile.lowering.stim.passes.scheduling import ChangeSchedulePass
from tqec.compile.lowering.stim.passes.sort_targets import SortTargetsPass
from tqec.compile.lowering.stim.passes.transformer import ScheduleConstant
from tqec.utils.enums import Basis


def _add_hadamard(mergeable_instructions: frozenset[str]) -> frozenset[str]:
    return mergeable_instructions | frozenset(["H"])


CSSPlaquetteCompiler: Final[PlaquetteCompiler] = PlaquetteCompiler(
    "CSS",
    [
        # Move schedules to have an empty schedule for basis change after resets
        # and before measurements.
        ChangeSchedulePass({0: 0, 6: 8} | {i: i + 1 for i in range(1, 6)}),
        # Change reset basis when needed
        ChangeResetBasisPass(Basis.Z),
        # Change measurement basis when needed
        ChangeMeasurementBasisPass(Basis.Z),
        # Change controlled gate basis when needed (CZ -> CX)
        ChangeControlledGateBasisPass(Basis.X, ScheduleConstant(1), ScheduleConstant(7)),
        # Sort the instruction targets to normalize the circuits.
        SortTargetsPass(),
    ],
    mergeable_instructions_modifier=_add_hadamard,
)
