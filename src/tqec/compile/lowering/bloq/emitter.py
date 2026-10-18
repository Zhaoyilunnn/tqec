"""Lower construction trees directly to the native Bloq text format."""

from importlib import import_module
from importlib.metadata import version

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.blocks.positioning import LayoutCubePosition2D
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.detectors import qec_relations
from tqec.compile.lowering.bloq.flows import _dependencies
from tqec.compile.lowering.bloq.layout import detector_regions, layout_moments
from tqec.compile.lowering.bloq.measurements import MeasurementRegistry
from tqec.compile.lowering.bloq.observables import observable_nodes
from tqec.compile.lowering.bloq.schedule import circuit_text
from tqec.compile.lowering.bloq.text import PINNED_BLOQ_VERSION, template, token
from tqec.compile.tree.tree import LayerTree
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
            raise UnsupportedLoweringError("bloq", "repeat", "negative count", path)
        for index in range(count):
            yield None
            yield from _events(layer.internal_layer, k, (*path, "repeat", index))
    else:
        raise UnsupportedLoweringError(
            "bloq", type(layer).__name__, "requires a spec-backed layout", path
        )


def _layers(layer, k: int):
    return (event for event in _events(layer, k) if event is not None)


def _timed_layers(layer, k: int, max_instances: int):
    ticks = 0
    first = True
    for count, event in enumerate(_events(layer, k)):
        if count >= 4 * (max_instances + 1):
            raise UnsupportedLoweringError(
                "bloq", "time expansion", "too many separators for the instance budget"
            )
        if event is None:
            ticks += 1
            continue
        if not first and ticks == 0:
            raise UnsupportedLoweringError(
                "bloq", "time boundary", "adjacent slices share a moment", event[0]
            )
        # Bloq terminates each template with one TICK. Preserve extra separators
        # contributed by nested sequences, including zero-repeat children.
        yield event, ticks if first else ticks - 1
        ticks = 0
        first = False


def emit_bloq_text(
    tree: LayerTree,
    k: int,
    *,
    gates_only: bool = False,
    reschedule_measurements: bool = True,
    max_instances: int = 10000,
    max_plaquettes: int = 100000,
    max_qubits: int = 2048,
) -> str:
    """Emit Bloq text without importing Bloq or Stim.

    ``gates_only=True`` explicitly requests physical operations without QEC side
    tables. Repetitions are bounded and unrolled into distinct instances; identical
    circuit templates are shared. No loop-carried measurement identity is invented.
    """
    if any(
        type(value) is not int or value < 1
        for value in (k, max_instances, max_plaquettes, max_qubits)
    ):
        raise ValueError("k and expansion budgets must be positive integers.")
    cells = 0
    qubits = set()
    layers = []
    all_moments = []
    circuits = []
    registry = MeasurementRegistry()
    for index, ((path, layer), padding) in enumerate(
        _timed_layers(tree.construction_root, k, max_instances)
    ):
        if index >= max_instances:
            raise UnsupportedLoweringError(
                "bloq", "repeat expansion", f"exceeds {max_instances} instances", path
            )
        if not all(isinstance(child, SpecPlaquetteLayer) for child in layer.layers.values()):
            raise UnsupportedLoweringError(
                "bloq", "concrete layer", "requires construction specs", path
            )
        # Check the dense template's size before allocating its index array.
        resolved, _ = layer.to_template_and_specs()
        shape = resolved.shape(k)
        cells += shape.x * shape.y
        if cells > max_plaquettes:
            raise UnsupportedLoweringError(
                "bloq", "spatial expansion", f"exceeds {max_plaquettes} plaquette cells", path
            )
        layers.append((path, layer))
        moments = [[] for _ in range(padding)] + layout_moments(
            layer, k, reschedule_measurements, path
        )
        qubits.update(q for moment in moments for _, targets in moment for q in targets)
        if len(qubits) > max_qubits:
            raise UnsupportedLoweringError(
                "bloq", "qubit expansion", f"exceeds {max_qubits} qubits", path
            )
        all_moments.append(moments)
        lines, records = circuit_text(moments)
        circuits.append(lines)
        registry.add_instance(index, records)
    if gates_only:
        tables, checks = ([[] for _ in layers], [[] for _ in layers])
    else:
        tables, checks, detector_parities = qec_relations(
            all_moments, registry, [list(detector_regions(layer, k)) for _, layer in layers]
        )
        observable_lines, logical_parities = observable_nodes(tree, k, layers, registry)
        for relation in _dependencies(detector_parities + logical_parities):
            if relation >> len(detector_parities):
                raise UnsupportedLoweringError(
                    "bloq", "logical boundary", "observable is contained in the detector space"
                )
    pool: dict = {}
    nodes = []
    for index, (lines, side_tables) in enumerate(zip(circuits, tables)):
        signature = (tuple(lines), tuple(side_tables))
        template_id = pool.setdefault(signature, len(pool))
        nodes.extend([f"  n{index} quantum {{", f"    instance i{index} t{template_id} @ (0,0)"])
        path, layer = layers[index]
        blocks = sorted(
            (position.to_block_position().x, position.to_block_position().y, path[0])
            for position in layer.layers
            if isinstance(position, LayoutCubePosition2D)
        )
        if blocks:
            nodes.append("    from blocks " + " ".join(f"({x},{y},{z})" for x, y, z in blocks))
        nodes.extend(f"    {check}" for check in checks[index])
        nodes.append("  }")
        if index:
            nodes.append(f"  n{index - 1} -> n{index} order")
    if not gates_only:
        nodes.extend(observable_lines)
    capability = "gates-only" if gates_only else "static-clifford"
    metadata = [
        "BLOQIR 1",
        f"metadata tqec.scale u64 {k}",
        f"metadata tqec.capability string {capability}",
        f"metadata tqec.bloq_version string {token(PINNED_BLOQ_VERSION)}",
    ]
    return (
        "\n\n".join(
            [
                *metadata,
                *(template(i, lines, sides) for (lines, sides), i in pool.items()),
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
    installed = version("bloq-py")
    if installed != PINNED_BLOQ_VERSION:
        raise TQECError(
            f"Bloq text loading requires bloq-py=={PINNED_BLOQ_VERSION}, found {installed}."
        )
    program = bloq.Bloq.from_text(text)
    if validate:
        program.validate()
    return program
