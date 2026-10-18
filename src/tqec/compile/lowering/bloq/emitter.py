"""Lower construction trees directly to the native Bloq text format."""

from importlib import import_module

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.layout import layout_moments
from tqec.compile.lowering.bloq.schedule import circuit_text
from tqec.compile.lowering.bloq.text import PINNED_BLOQ_VERSION, template, token
from tqec.compile.tree.tree import LayerTree
from tqec.utils.exceptions import TQECError
from tqec.utils.scale import round_or_fail


def _layers(layer, k: int, path: tuple = ()):
    if isinstance(layer, LayoutLayer):
        yield path, layer
    elif isinstance(layer, SequencedLayers):
        for index, child in enumerate(layer.layer_sequence):
            yield from _layers(child, k, (*path, index))
    elif isinstance(layer, RepeatedLayer):
        count = round_or_fail(layer.repetitions(k))
        if count < 0:
            raise UnsupportedLoweringError("bloq", "repeat", "negative count", path)
        for index in range(count):
            yield from _layers(layer.internal_layer, k, (*path, "repeat", index))
    else:
        raise UnsupportedLoweringError(
            "bloq", type(layer).__name__, "requires a spec-backed layout", path
        )


def emit_bloq_text(
    tree: LayerTree,
    k: int,
    *,
    gates_only: bool = False,
    reschedule_measurements: bool = True,
    max_instances: int = 10000,
) -> str:
    """Emit Bloq text without importing Bloq or Stim.

    ``gates_only=True`` explicitly requests physical operations without QEC side
    tables. Repetitions are bounded and unrolled into distinct instances; identical
    circuit templates are shared. No loop-carried measurement identity is invented.
    """
    if type(k) is not int or k < 1 or type(max_instances) is not int or max_instances < 1:
        raise ValueError("k and max_instances must be positive integers.")
    if not gates_only:
        raise UnsupportedLoweringError(
            "bloq", "QEC side tables", "complete lowering is not implemented"
        )
    pool: dict = {}
    nodes = []
    for index, (path, layer) in enumerate(_layers(tree.construction_root, k)):
        if index >= max_instances:
            raise UnsupportedLoweringError(
                "bloq", "repeat expansion", f"exceeds {max_instances} instances", path
            )
        moments = layout_moments(layer, k, reschedule_measurements, path)
        lines, _ = circuit_text(moments)
        signature = tuple(lines)
        template_id = pool.setdefault(signature, len(pool))
        nodes.extend(
            [f"  n{index} quantum {{", f"    instance i{index} t{template_id} @ (0,0)", "  }"]
        )
        if index:
            nodes.append(f"  n{index - 1} -> n{index} order")
    metadata = [
        "BLOQIR 1",
        f"metadata tqec.scale u64 {k}",
        "metadata tqec.capability string gates-only",
        f"metadata tqec.bloq_version string {token(PINNED_BLOQ_VERSION)}",
    ]
    return (
        "\n\n".join(
            [
                *metadata,
                *(template(i, lines) for lines, i in pool.items()),
                "graph {\n" + "\n".join(nodes) + "\n}",
            ]
        )
        + "\n"
    )


def lower_to_bloq(tree: LayerTree, k: int, *, validate: bool = True, **kwargs):
    """Load emitted text through the optional, pinned Bloq Python binding."""
    text = emit_bloq_text(tree, k, **kwargs)
    try:
        bloq = import_module("bloq")
    except ModuleNotFoundError as error:
        raise TQECError("Bloq loading requires bloq-py==0.1.1; text emission does not.") from error
    program = bloq.Bloq.from_text(text)
    if validate:
        program.validate()
    return program
