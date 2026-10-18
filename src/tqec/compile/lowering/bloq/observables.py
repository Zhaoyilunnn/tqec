"""Resolve abstract readouts at the instances that actually measure their qubits."""

from tqec.compile.lowering.bloq.measurements import MeasurementRegistry
from tqec.compile.observables.builder import ObservableComponent


def observable_nodes(tree, k: int, layers, registry: MeasurementRegistry):
    """Reuse correlation-surface geometry while selecting measurement owners per qubit."""
    result = []
    parities = []
    for observable_index, observable in enumerate(tree._abstract_observables):
        parity = 0
        for z in range(len(tree.construction_root.layer_sequence)):
            obs_slice = observable.slice_at_z(z)
            for component in ObservableComponent:
                selected = {}
                first_instance = next(i for i, (path, _) in enumerate(layers) if path[0] == z)
                for instance, (path, layer) in enumerate(layers):
                    if path[0] != z or (
                        component == ObservableComponent.BOTTOM_STABILIZERS
                        and instance != first_instance
                    ):
                        continue
                    template, _ = layer.to_template_and_specs()
                    qubits = tree._observable_builder.build(k, template, obs_slice, component)
                    for q in qubits:
                        records = registry.by_instance[instance].get((q.x, q.y), [])
                        if not records:
                            continue
                        if component == ObservableComponent.BOTTOM_STABILIZERS and q in selected:
                            continue
                        selected[q] = registry.offsets[instance] + records[-1][1]
                for record in selected.values():
                    parity ^= 1 << record
        parities.append(parity)
        node = len(layers) + observable_index
        result.append(
            f"  n{node} observable {observable_index} measurements {registry.parity(parity)}"
            f" from generator {observable_index}"
        )
        if layers:
            result.append(f"  n{len(layers) - 1} -> n{node} order")
    return result, parities
