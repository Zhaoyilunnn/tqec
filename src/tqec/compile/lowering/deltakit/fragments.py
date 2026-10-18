"""Native reusable circuits for complete spatial time slices."""
# ruff: noqa: PLC0415

from tqec.compile.lowering.deltakit.annotations import boundary_flows


def build_fragment(name, coords, moments, annotate):
    """Return a native circuit with returned measurement SSA and proven boundaries."""
    from deltakit_compile.dialects.stim import TickAnnotationOp
    from deltakit_compile.frontend.circuit import CircuitBuilder, ParallelAlignment, QubitReg

    builder = CircuitBuilder()
    register = builder.add_arg(QubitReg(len(coords)))
    qubits = {q: register[i] for i, q in enumerate(coords)}
    records = []
    ownership = []
    for moment in moments:
        if not moment:
            builder._builder.append_ops_ignoring_ssas(TickAnnotationOp())
            continue
        with builder.parallel(ParallelAlignment.LOCKSTEP) as parallel:
            for gate, targets in moment:
                with parallel():
                    if gate.startswith("M"):
                        ownership.append(targets[0])
                        records.append(
                            builder.measure("Z" if gate == "M" else gate[-1], qubits[targets[0]])
                        )
                    else:
                        builder.gate("RZ" if gate == "R" else gate, [qubits[q] for q in targets])
    builder.add_return(records)
    flows = boundary_flows(builder, qubits, coords, moments, records) if annotate else ([], [])
    return builder.build(name), flows, ownership
