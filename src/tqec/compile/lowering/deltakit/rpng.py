"""Translate RPNG construction parameters directly into temporary scheduled operations."""

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.plaquette.qubit import SquarePlaquetteQubits
from tqec.plaquette.spec import RPNGPlaquetteSpec


def rpng_operations(spec: RPNGPlaquetteSpec) -> dict:
    """Expand one square plaquette without constructing a physical circuit object."""
    qubits = SquarePlaquetteQubits()
    data = [(q.x, q.y) for q in qubits.data_qubits]
    ancilla = (qubits.syndrome_qubits[0].x, qubits.syndrome_qubits[0].y)
    result: dict = {0: []}
    description = spec.description
    for timestep, part, prefix in ((0, "r", "R"), (spec.measurement_schedule, "g", "M")):
        for q, basis in [(ancilla, getattr(description.ancilla, part))] + [
            (q, getattr(corner, part)) for q, corner in zip(data, description.corners)
        ]:
            if basis is not None:
                suffix = basis.value.upper()
                gate = "H" if suffix == "H" else prefix + (suffix if suffix != "Z" else "")
                result.setdefault(timestep, []).append((gate, (q,)))
    occupied = set()
    for q, corner in zip(data, description.corners):
        if corner.p is None or corner.n is None:
            continue
        if corner.n in occupied or not 0 < corner.n < spec.measurement_schedule:
            raise UnsupportedLoweringError("deltakit", "RPNG", "invalid entangling schedule")
        occupied.add(corner.n)
        result.setdefault(corner.n, []).append(("C" + corner.p.value.upper(), (ancilla, q)))
    return result
