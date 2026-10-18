"""Direct schedules for the two halves of extended stabilizer constructions."""

from tqec.plaquette.spec import ExtendedPlaquetteSpec
from tqec.utils.enums import Orientation


def extended_operations(spec: ExtendedPlaquetteSpec) -> dict:
    """Preserve internal GHZ operations, reversal, orientation and shaped data support."""
    side = 1 if spec.second else -1
    if spec.orientation == Orientation.VERTICAL:
        data = ((-1, side), (1, side))
        other = ((-1, -side), (1, -side))
        corners = spec.description.corners[2:] if spec.second else spec.description.corners[:2]
    else:
        data = ((side, -1), (side, 1))
        other = ((-side, -1), (-side, 1))
        a, b = (1, 3) if spec.second else (0, 2)
        corners = (spec.description.corners[a], spec.description.corners[b])
    s1, s2 = (0, 0), other[spec.is_reversed]
    result: dict = {t: [] for t in range(8)}
    result[0].append(("R", (s2,)))
    operations = spec.data_operations.second if spec.second else spec.data_operations.first
    if operations.reset is not None:
        result[0].extend(
            ("R" + (operations.reset.value if operations.reset.value != "Z" else ""), (q,))
            for q in data
        )
    if spec.is_reversed == spec.second:
        result[0].append(("RX", (s1,)))
        result[1].append(("CX", (s1, s2)))
        result[5].append(("CX", (s2, s1)))
    else:
        result[1].append(("R", (s1,)))
        result[2].append(("CX", (s2, s1)))
        result[6].append(("CX", (s1, s2)))
        result[7].append(("MX", (s1,)))
    for q, corner in zip(data, corners):
        if corner.p is not None and corner.n is not None:
            result[corner.n].append(("C" + corner.p.value.upper(), (s1, q)))
    if operations.measurement is not None:
        result[7].extend(
            (
                "M" + (operations.measurement.value if operations.measurement.value != "Z" else ""),
                (q,),
            )
            for q in data
        )
    if spec.measurement is not None:
        result[7].extend(
            ("M", (q,)) for q in ((s1, s2) if spec.is_reversed == spec.second else (s2,))
        )
    keep = {(q.x, q.y) for q in spec.used_qubits}
    filtered = {
        t: [(g, qs) for g, qs in ops if all(q in keep for q in qs)] for t, ops in result.items()
    }
    # Shaped projection drops trailing empty moments; this matches the
    # construction's documented num_moments rather than padding every half to 8.
    return {t: ops for t, ops in filtered.items() if t < spec.num_moments}
