"""Explicit capability and work limits for native Deltakit lowering."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DeltakitOptions:
    """Select annotation semantics without silently dropping logical observables."""

    annotation_mode: Literal["none", "explicit", "auto"] = "none"
    include_observables: bool | None = None
    repeat_mode: Literal["unroll"] = "unroll"
    strict_schedule: bool = True
    reschedule_measurements: bool = True
    max_unrolled_rounds: int = 1000
    max_plaquettes: int = 100000
    max_qubits: int = 2048
