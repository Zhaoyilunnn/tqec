"""Prove local parity relations and attach them to native measurement SSA values."""

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.deltakit.flows import _dependencies, closed_relations, fragment_flows
from tqec.compile.lowering.deltakit.neighborhoods import detector_regions


def indices(mask):
    """Enumerate a nonnegative measurement mask."""
    if mask < 0:
        raise ValueError("Negative measurement mask.")
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def boundary_flows(builder, qubits, coords, moments, records):
    """Declare signed creation and destruction flows after registering returns."""
    creation, destruction = fragment_flows(moments, coords)
    for flows, incoming in ((creation, False), (destruction, True)):
        for x, z, mask, sign in flows:
            if not x | z:
                continue
            paulis = {
                qubits[q]: "IXZY"[((x >> i) & 1) + 2 * ((z >> i) & 1)]
                for i, q in enumerate(coords)
                if (x | z) >> i & 1
            }
            builder.add_flow(
                paulis if incoming else {},
                {} if incoming else paulis,
                [records[i] for i in indices(mask)],
                parity=not sign,
            )
    return creation, destruction


def detector_recipes(layers, k, families, ownership, offsets, coords):
    """Intersect closed stabilizer relations with construction-owned local checks."""
    previous = []
    seen = {}
    for instance, ((incoming_creation, incoming_destruction), (path, layer)) in enumerate(
        zip(families, layers)
    ):
        creation = [(x, z, m << offsets[instance], sign) for x, z, m, sign in incoming_creation]
        destruction = [
            (x, z, m << offsets[instance], sign) for x, z, m, sign in incoming_destruction
        ]
        candidates = [
            relation
            for family in (creation, destruction, previous + destruction)
            for relation in closed_relations(family, len(coords))
        ]
        begin = offsets[max(0, instance - 1)]
        end = offsets[instance + 1] if instance + 1 < len(offsets) else len(ownership)
        for center, (rx, ry), syndrome in detector_regions(layer, k):
            allowed = owned = 0
            for record in range(begin, end):
                q = ownership[record]
                if abs(q[0] - center[0]) <= rx and abs(q[1] - center[1]) <= ry:
                    allowed |= 1 << record
                if q in syndrome:
                    owned |= 1 << record
            for combination in _dependencies([mask & ~allowed for mask, _ in candidates]):
                mask = sign = 0
                for i in indices(combination):
                    parity, negative = candidates[i]
                    mask ^= parity
                    sign ^= negative
                if not mask or not mask & owned:
                    continue
                if mask in seen:
                    if seen[mask] != sign:
                        raise UnsupportedLoweringError(
                            "deltakit", "detector", "conflicting signs", path
                        )
                    continue
                if sign:
                    raise UnsupportedLoweringError(
                        "deltakit",
                        "detector",
                        "signed detectors need an explicit native correction",
                        path,
                    )
                seen[mask] = sign
                yield mask, (*center, instance)
        previous = creation
