"""Merge ephemeral operations while retaining TQEC moment boundaries."""

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.text import operation


def merge_moment(operations: list, location: tuple) -> list:
    """Deduplicate shared resets, measurements and H, rejecting other overlap."""
    merged: dict = {}
    occupied: dict = {}
    for gate, targets in operations:
        key = (gate, targets)
        if key in merged and gate in {"R", "RX", "RY", "M", "MX", "MY", "H"}:
            continue
        for q in targets:
            if q in occupied:
                raise UnsupportedLoweringError(
                    "bloq",
                    "moment",
                    f"conflicting operations on {q}: {occupied[q]} and {gate}",
                    location,
                )
            occupied[q] = gate
        merged[key] = None
    return sorted(merged)


def circuit_text(moments: list[list]) -> tuple[list[str], dict]:
    """Assign a distinct record to each actual measurement after spatial merging."""
    lines = []
    records: dict = {}
    next_measurement = 0
    for timestep, moment in enumerate(moments):
        if timestep:
            lines.append("TICK")
        for gate, targets in moment:
            ids = ()
            if gate.startswith("M"):
                ids = tuple(range(next_measurement, next_measurement + len(targets)))
                next_measurement += len(targets)
                for q, index in zip(targets, ids):
                    records.setdefault(q, []).append((timestep, index, gate))
            lines.append(operation(gate, targets, ids))
    return lines, records
