"""Read-only expansion of construction time boundaries."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.lowering.base import UnsupportedLoweringError
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
            raise UnsupportedLoweringError("deltakit", "repeat", "negative count", path)
        for index in range(count):
            yield None
            yield from _events(layer.internal_layer, k, (*path, "repeat", index))
    else:
        raise UnsupportedLoweringError(
            "deltakit", type(layer).__name__, "requires a spec-backed layout", path
        )


def _layers(layer, k: int):
    return (event for event in _events(layer, k) if event is not None)


def _timed_layers(layer, k: int, max_instances: int):
    ticks = 0
    first = True
    for count, event in enumerate(_events(layer, k)):
        if count >= 4 * (max_instances + 1):
            raise UnsupportedLoweringError(
                "deltakit", "time expansion", "too many separators for the instance budget"
            )
        if event is None:
            ticks += 1
            continue
        if not first and ticks == 0:
            raise UnsupportedLoweringError(
                "deltakit", "time boundary", "adjacent slices share a moment", event[0]
            )
        # Native export terminates each nonempty moment with one TICK. Preserve extra separators
        # contributed by nested sequences, including zero-repeat children.
        yield event, ticks if first else ticks - 1
        ticks = 0
        first = False
