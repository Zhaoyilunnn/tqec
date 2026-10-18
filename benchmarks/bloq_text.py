"""Measure bounded Bloq emission: python benchmarks/bloq_text.py."""

import re
from time import perf_counter
from tracemalloc import get_traced_memory, start, stop

from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.bloq import emit_bloq_text
from tqec.compile.tree.tree import LayerTree
from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import Position3D
from tqec.utils.scale import LinearFunction


def main() -> None:
    """Report text pool sizes, serialization time and traced Python allocations."""
    graph = BlockGraph()
    graph.add_cube(Position3D(0, 0, 0), "XZZ")
    tree = compile_block_graph(graph).to_layer_tree()
    sequence = tree.construction_root.layer_sequence[0]
    assert isinstance(sequence, SequencedLayers)
    first, middle, last = sequence.layer_sequence
    assert isinstance(middle, RepeatedLayer)
    long_tree = LayerTree(
        SequencedLayers(
            [
                SequencedLayers(
                    [first, RepeatedLayer(middle.internal_layer, LinearFunction(0, 100)), last]
                )
            ]
        ),
        tree._observable_builder,
        tree._abstract_observables,
    )
    for name, construction, k in (("memory-k2", tree, 2), ("memory-100-rounds", long_tree, 1)):
        start()
        begin = perf_counter()
        text = emit_bloq_text(construction, k)
        elapsed = perf_counter() - begin
        _, peak = get_traced_memory()
        stop()
        print(
            {
                "case": name,
                "templates": len(re.findall(r"^template ", text, re.MULTILINE)),
                "instances": len(re.findall(r"^    instance ", text, re.MULTILINE)),
                "stored_detectors": len(re.findall(r"^ +detector ", text, re.MULTILINE)),
                "text_bytes": len(text.encode()),
                "seconds": round(elapsed, 3),
                "peak_python_mib": round(peak / 2**20, 3),
            }
        )


if __name__ == "__main__":
    main()
