"""Close proven fragment boundary relations using actual instance records."""

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.flows import closed_relations, fragment_flows
from tqec.compile.lowering.bloq.measurements import MeasurementRegistry, indices
from tqec.compile.lowering.bloq.text import coordinate


def _pauli_text(x, z, qubits):
    return (
        "*".join(
            f"{'IXZY'[((x >> i) & 1) + 2 * ((z >> i) & 1)]}{coordinate(q)}"
            for i, q in enumerate(qubits)
            if (x | z) >> i & 1
        )
        or "_"
    )


def qec_relations(all_moments, registry: MeasurementRegistry):
    """Return template flows, local checks and checks spanning adjacent instances."""
    qubits = sorted(
        {
            q
            for moments in all_moments
            for moment in moments
            for _, targets in moment
            for q in targets
        }
    )
    template_tables = [[] for _ in all_moments]
    node_tables = [[] for _ in all_moments]
    previous = []
    seen = {}
    for instance, moments in enumerate(all_moments):
        creation, destruction = fragment_flows(moments, qubits)
        offset = registry.offsets[instance]
        creation = [(x, z, m << offset, sign) for x, z, m, sign in creation]
        destruction = [(x, z, m << offset, sign) for x, z, m, sign in destruction]
        for family, incoming in ((creation, False), (destruction, True)):
            for x, z, mask, sign in family:
                if not (x | z):
                    continue
                p = _pauli_text(x, z, qubits)
                start, end = (p, "_") if incoming else ("_", p)
                measurements = (
                    f" meas {registry.parity(mask, local_instance=instance)}" if mask else ""
                )
                template_tables[instance].append(
                    f"flow {start} -> {end}{measurements}" + (" sign -1" if sign else "")
                )
        for family in (creation, destruction, previous + destruction):
            for mask, sign in closed_relations(family, len(qubits)):
                if mask in seen:
                    if seen[mask] != sign:
                        raise UnsupportedLoweringError(
                            "bloq", "detector", "inconsistent parity signs", instance
                        )
                    continue
                seen[mask] = sign
                records = [registry.outputs[i] for i in indices(mask)]
                # The latest owned measurement anchors the check in space; node
                # order supplies time. Bloq detector coordinates are two-dimensional.
                center = max(records, key=lambda item: (item[0], item[3], -item[1]))[2]
                local = all(owner == instance for owner, _, _, _ in records)
                parity = registry.parity(mask, local_instance=instance if local else None)
                line = f"detector {'-' if sign else ''}{parity} @ {coordinate(center)}"
                (template_tables if local else node_tables)[instance].append(line)
        previous = creation
    return template_tables, node_tables
