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
        raise TQECError(
            "deltakit", type(layer).__name__, "requires a concrete LayoutLayer", path
        )


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
            raise TQECError(
                "deltakit", "time boundary", "adjacent slices share a moment", event[0]
            )
        # Native export terminates each nonempty moment with one TICK. Preserve extra separators
        # contributed by nested sequences, including zero-repeat children.
        yield event, ticks if first else ticks - 1
        ticks = 0
        first = False


def build_native(tree, k, max_rounds=1000, reschedule_measurements=True):
    """Assemble concrete plaquette circuits while retaining the original layer tree."""
    from tqec.circuit.native import assemble, compile_module
    from tqec.circuit.qubit_map import QubitMap

    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer.")
    if type(max_rounds) is not int or max_rounds < 1:
        raise ValueError("max_rounds must be a positive integer.")
    instances = []
    cache = {}
    for index, ((path, layer), padding) in enumerate(_timed_layers(tree._root._layer, k, max_rounds)):
        if index >= max_rounds:
            raise TQECError("Native expansion exceeded the round budget.")
        if id(layer) not in cache:
            cache[id(layer)] = layer.to_circuit(k, reschedule_measurements=reschedule_measurements)
        instances.append((path, layer, padding, cache[id(layer)]))
    qubits = sorted({q for _, _, _, circuit in instances for q in circuit.qubits})
    qubit_map = QubitMap.from_qubits(qubits)
    moments = []
    for path, layer, padding, circuit in instances:
        mapped = circuit.map_qubit_indices({i: qubit_map[q] for i, q in circuit.qubit_map.items()})
        by_time = dict(mapped.scheduled_moments)
        moments.extend([None] * padding)
        moments.extend(by_time.get(t) for t in range(mapped.schedule.max_schedule + 1))
    return compile_module(assemble(moments, qubit_map)).module
