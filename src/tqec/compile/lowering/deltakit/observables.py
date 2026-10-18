"""Bind correlation-surface readouts to actual Deltakit measurement owners."""

from tqec.compile.observables.builder import ObservableComponent


def observable_records(tree, k, layers, records_by_layer):
    """Resolve parity recipes in source order, using each contribution's time slice."""
    for observable in tree._abstract_observables:
        parity = set()
        for z in range(len(tree.construction_root.layer_sequence)):
            sliced = observable.slice_at_z(z)
            first = next(i for i, (path, _) in enumerate(layers) if path[0] == z)
            for component in ObservableComponent:
                selected = {}
                for index, (path, layer) in enumerate(layers):
                    if path[0] != z or (
                        component == ObservableComponent.BOTTOM_STABILIZERS and index != first
                    ):
                        continue
                    template, _ = layer.to_template_and_specs()
                    for qubit in tree._observable_builder.build(k, template, sliced, component):
                        records = records_by_layer[index].get((qubit.x, qubit.y), [])
                        if records:
                            selected[qubit] = records[-1]
                parity.symmetric_difference_update(selected.values())
        yield sorted(parity)
