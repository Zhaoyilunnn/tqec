# ruff: noqa: PLC0415
"""Read-only expansion of construction time boundaries."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import round_or_fail


def _events(layer, k: int, path: tuple = ()):
    if isinstance(layer, LayoutLayer):
        yield path, layer
    elif isinstance(layer, SequencedLayers):
        children = layer.layer_sequence
        for index, child in enumerate(children):
            yield from _events(child, k, (*path, index))
            if index + 1 < len(children) and not isinstance(children[index + 1], RepeatedLayer):
                yield None
    elif isinstance(layer, RepeatedLayer):
        count = round_or_fail(layer.repetitions(k))
        if count < 0:
            raise TQECError("deltakit", "repeat", "negative count", path)
        for index in range(count):
            yield None
            yield from _events(layer.internal_layer, k, (*path, "repeat", index))
    else:
        raise TQECError("deltakit", type(layer).__name__, "requires a concrete LayoutLayer", path)


def _layers(layer, k: int):
    return (event for event in _events(layer, k) if event is not None)


def _timed_layers(layer, k: int, max_instances: int):
    ticks = 0
    first = True
    for count, event in enumerate(_events(layer, k)):
        if count >= 4 * (max_instances + 1):
            raise TQECError(
                "deltakit", "time expansion", "too many separators for the instance budget"
            )
        if event is None:
            ticks += 1
            continue
        if not first and ticks == 0:
            raise TQECError("deltakit", "time boundary", "adjacent slices share a moment", event[0])
        # Native export terminates each nonempty moment with one TICK. Preserve extra separators
        # contributed by nested sequences, including zero-repeat children.
        yield event, ticks if first else ticks - 1
        ticks = 0
        first = False


def _observable_parities(tree, k, instances, offsets):
    from tqec.circuit.measurement_map import MeasurementRecordsMap
    from tqec.compile.observables.builder import ObservableComponent

    records = [
        MeasurementRecordsMap.from_scheduled_circuit(circuit).mapping
        for _, _, _, circuit in instances
    ]
    for observable in tree._abstract_observables:
        parity = set()
        for z in range(len(tree._root._layer.layer_sequence)):
            sliced = observable.slice_at_z(z)
            first = next(i for i, (path, _, _, _) in enumerate(instances) if path[0] == z)
            for component in ObservableComponent:
                selected = {}
                for index, (path, layer, _, circuit) in enumerate(instances):
                    if path[0] != z or (
                        component == ObservableComponent.BOTTOM_STABILIZERS and index != first
                    ):
                        continue
                    template, _ = layer.to_template_and_plaquettes()
                    for qubit in tree._observable_builder.build(k, template, sliced, component):
                        if qubit in records[index]:
                            selected[qubit] = offsets[index] + records[index][qubit][-1]
                parity.symmetric_difference_update(selected.values())
        yield sorted(parity)


def build_native(
    tree,
    k,
    max_rounds=1000,
    reschedule_measurements=True,
    annotation_mode="none",
    include_observables=False,
    manhattan_radius=2,
    detector_database=None,
    lookback=2,
):
    """Build physical IR first, then attach explicitly selected annotation semantics."""
    from deltakit_compile.dialects import qec, qstruct
    from deltakit_compile.dialects.stim import ObservableIdAttr
    from xdsl.dialects.builtin import StringAttr

    from tqec.circuit.native import assemble, compile_module
    from tqec.circuit.qubit_map import QubitMap
    from tqec.compile.detectors.database import DetectorDatabase
    from tqec.compile.tree.annotators.observables import get_ordered_leaves

    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer.")
    if type(max_rounds) is not int or max_rounds < 1:
        raise ValueError("max_rounds must be a positive integer.")
    if annotation_mode not in {"none", "legacy", "auto"}:
        raise ValueError("annotation_mode must be none, legacy or auto.")
    if annotation_mode == "auto" and include_observables:
        raise TQECError("Experimental auto finding cannot preserve logical observables.")
    instances = []
    cache = {}
    for index, ((path, layer), padding) in enumerate(
        _timed_layers(tree._root._layer, k, max_rounds)
    ):
        if index >= max_rounds:
            raise TQECError("Native expansion exceeded the round budget.")
        template, _ = layer.to_template_and_plaquettes()
        shape = template.shape(k)
        if shape.x * shape.y > 100000:
            raise TQECError("Native layout exceeded the 100000 cell budget.")
        if id(layer) not in cache:
            cache[id(layer)] = layer.to_circuit(k, reschedule_measurements=reschedule_measurements)
        instances.append((path, layer, padding, cache[id(layer)]))
    qubits = sorted({q for _, _, _, circuit in instances for q in circuit.qubits})
    if len(qubits) > 2048:
        raise TQECError("Native program exceeded the 2048 qubit budget.")
    qubit_map = QubitMap.from_qubits(qubits)
    moments = []
    offsets = []
    measured = 0
    for path, layer, padding, circuit in instances:
        mapped = circuit.map_qubit_indices({i: qubit_map[q] for i, q in circuit.qubit_map.items()})
        by_time = dict(mapped.scheduled_moments)
        moments.extend([None] * padding)
        moments.extend(by_time.get(t) for t in range(mapped.schedule.max_schedule + 1))
        measured += mapped.num_measurements
        offsets.append(measured)
    # Complete and verify the physical program before the compatibility finder
    # is allowed to export any fragment to its Stim-based analysis boundary.
    module = assemble(moments, qubit_map)
    annotations = {}
    if annotation_mode == "legacy":
        for node in get_ordered_leaves(tree._root):
            assert isinstance(node._layer, LayoutLayer)
            ann = node.get_annotations(k)
            if id(node._layer) not in cache:
                cache[id(node._layer)] = node._layer.to_circuit(
                    k, reschedule_measurements=reschedule_measurements
                )
            ann.circuit = cache[id(node._layer)]
            ann.detectors.clear()
            annotations[id(node._layer)] = ann
        tree._annotate_detectors(
            k,
            manhattan_radius,
            detector_database if detector_database is not None else DetectorDatabase(),
            database_path=None,
            lookback=lookback,
        )

    def annotate(body, records):
        if annotation_mode == "legacy":
            for index, (_, layer, _, _) in enumerate(instances):
                for detector in annotations[id(layer)].detectors:
                    coords = detector.coordinates.to_stim_coordinates()
                    coords = (*coords[:2], coords[2] + index)
                    body.add_op(
                        qec.DetectorOp(
                            [records[offsets[index] + i] for i in detector.measurement_offsets],
                            [float(v) for v in coords],
                        )
                    )
        if include_observables:
            for index, parity in enumerate(_observable_parities(tree, k, instances, offsets)):
                declared = qec.DecObservableOp()
                ObservableIdAttr.set(declared, index)
                include = qec.ObservableIncludeOp(declared.result, [records[i] for i in parity])
                readout = qec.GetUncorrectedOp(include.out_obs)
                body.add_ops([declared, include, readout, qstruct.OutputOp([readout.result])])

    if annotation_mode == "legacy" or include_observables:
        module = assemble(moments, qubit_map, annotate)
    result = compile_module(module, auto=annotation_mode == "auto").module
    result.attributes["tqec.capability"] = StringAttr(
        {"none": "physical-only", "legacy": "legacy-detectors", "auto": "experimental-auto"}[
            annotation_mode
        ]
    )
    return result
