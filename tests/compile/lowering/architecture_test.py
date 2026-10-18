from unittest.mock import patch

import pytest
import stim

from tqec.circuit.moment import Moment
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BOUNDARY_CONVENTION, FIXED_BULK_CONVENTION
from tqec.computation.block_graph import BlockGraph
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.position import Position3D


def assert_specs(layer):
    if isinstance(layer, (SequencedLayers,)):
        for child in layer.layer_sequence:
            assert_specs(child)
    elif isinstance(layer, RepeatedLayer):
        assert_specs(layer.internal_layer)
    elif isinstance(layer, LayoutLayer):
        for child in layer.layers.values():
            assert isinstance(child, SpecPlaquetteLayer)
    else:
        assert isinstance(layer, SpecPlaquetteLayer)


@pytest.mark.parametrize("convention", (FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION))
@pytest.mark.parametrize("kind", ("memory", "hadamard", "junction"))
def test_compile_does_not_construct_physical_circuits(convention, kind):
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), "ZZX" if kind == "junction" else "XZZ")
    if kind == "hadamard":
        graph.add_pipe(first, graph.add_cube(Position3D(0, 0, 1), "ZXX"))
    if kind == "junction":
        for p in ((0, 1, 0), (-1, 0, 0), (1, 0, 0)):
            graph.add_pipe(first, graph.add_cube(Position3D(*p), "ZZX"))
    with (
        patch.object(stim, "Circuit", side_effect=AssertionError("Stim construction")),
        patch.object(Moment, "__init__", side_effect=AssertionError("Moment construction")),
        patch.object(ScheduledCircuit, "__init__", side_effect=AssertionError("ScheduledCircuit")),
        patch.object(DefaultRPNGTranslator, "translate", side_effect=AssertionError("translation")),
    ):
        compiled = compile_block_graph(graph, convention)
        tree = compiled.to_layer_tree()
        assert_specs(tree._root._layer)
