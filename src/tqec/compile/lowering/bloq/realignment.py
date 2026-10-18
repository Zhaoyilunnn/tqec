"""Direct seven-moment temporal-H realignment with boundary projection."""

from tqec.plaquette.spec import RealignmentPlaquetteSpec
from tqec.utils.enums import Basis, Orientation


def realignment_operations(spec: RealignmentPlaquetteSpec) -> dict:
    """Emit the established realignment interactions without a Stim intermediary."""
    qubits = ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0))
    pairs, times = {
        (Basis.Z, Orientation.VERTICAL): (((0, 4), (1, 4), (4, 2), (4, 0)), (1, 2, 3, 5)),
        (Basis.Z, Orientation.HORIZONTAL): (((0, 4), (2, 4), (4, 1), (4, 0)), (1, 3, 4, 5)),
        (Basis.X, Orientation.VERTICAL): (((4, 0), (4, 2), (1, 4), (0, 4)), (1, 3, 4, 5)),
        (Basis.X, Orientation.HORIZONTAL): (((4, 0), (4, 1), (2, 4), (0, 4)), (1, 2, 3, 5)),
    }[spec.stabilizer_basis, spec.z_orientation]
    result: dict = {
        0: [("R" + (spec.mq_reset.value if spec.mq_reset != Basis.Z else ""), (qubits[4],))]
    }
    for (a, b), time in zip(pairs, times):
        result[time] = [("CX", (qubits[a], qubits[b]))]
    result[6] = [
        ("M" + (spec.mq_measurement.value if spec.mq_measurement != Basis.Z else ""), (qubits[4],))
    ]
    result[6].extend(("H", (q,)) for q in qubits[:4])
    keep = {(q.x, q.y) for q in spec.used_qubits}
    return {
        t: [(g, qs) for g, qs in ops if all(q in keep for q in qs)] for t, ops in result.items()
    }
