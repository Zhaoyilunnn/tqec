"""Merge ephemeral operations while retaining TQEC moment boundaries."""

from tqec.compile.lowering.base import UnsupportedLoweringError


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
                    "deltakit",
                    "moment",
                    f"conflicting operations on {q}: {occupied[q]} and {gate}",
                    location,
                )
            occupied[q] = gate
        merged[key] = None
    return sorted(merged)
