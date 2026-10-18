import subprocess
import sys
from typing import cast

import pytest

from tests.compile.decoupling_baseline_test import make_graph
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq import emit_bloq_text
from tqec.compile.lowering.bloq.emitter import _timed_layers
from tqec.compile.lowering.bloq.measurements import MeasurementRegistry
from tqec.compile.lowering.bloq.schedule import circuit_text, merge_moment
from tqec.compile.lowering.stim.materializer import StimMaterializer
from tqec.compile.tree.tree import LayerTree
from tqec.utils.scale import LinearFunction


def test_cold_import_without_backends() -> None:
    script = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if (fullname.split('.')[0] in {'stim', 'tqecd', 'bloq'}
                or fullname.startswith('tqec.compile.lowering.stim')):
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, Block())
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.bloq import emit_bloq_text, lower_to_bloq
from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import Position3D
from tqec.utils.exceptions import TQECError
for case in ('memory', 'junction', 'hadamard'):
    graph = BlockGraph()
    first = graph.add_cube(Position3D(0, 0, 0), 'ZZX' if case == 'junction' else 'XZZ')
    if case == 'junction':
        for pos in ((0, 1, 0), (-1, 0, 0), (1, 0, 0)):
            graph.add_pipe(first, graph.add_cube(Position3D(*pos), 'ZZX'))
    if case == 'hadamard':
        graph.add_pipe(first, graph.add_cube(Position3D(0, 0, 1), 'ZXX'))
    tree = compile_block_graph(graph).to_layer_tree()
    assert 'observable' in emit_bloq_text(tree, 1)
try:
    lower_to_bloq(tree, 1)
except TQECError as error:
    assert 'bloq-py==0.1.1' in str(error)
else:
    raise AssertionError('missing optional dependency was ignored')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False, timeout=25
    )
    assert result.returncode == 0, result.stderr


def test_merge_measurement_identity_and_empty_ticks() -> None:
    q = (2, -3)
    merged = merge_moment([("MX", (q,)), ("MX", (q,))], (0,))
    lines, records = circuit_text([[], [], merged])
    assert lines == ["TICK", "TICK", "MX (2,-3):m0"]
    registry = MeasurementRegistry()
    registry.add_instance(0, records)
    registry.add_instance(1, records)
    assert registry.parity(3) == "i0:m0*i1:m0"
    with pytest.raises(ValueError, match="another instance"):
        registry.parity(3, local_instance=0)
    with pytest.raises(ValueError, match="Undefined"):
        registry.parity(4)
    with pytest.raises(ValueError, match="unique"):
        registry.add_instance(1, records)
    with pytest.raises(UnsupportedLoweringError, match="conflicting"):
        merge_moment([("MX", (q,)), ("M", (q,))], (0,))
    with pytest.raises(UnsupportedLoweringError, match="conflicting"):
        merge_moment([("CX", (q, (0, 0))), ("CX", (q, (0, 0)))], (0,))


def test_repetition_budget() -> None:
    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    with pytest.raises(UnsupportedLoweringError, match="exceeds 1 instances"):
        emit_bloq_text(tree, 1, max_instances=1)
    for scale in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            emit_bloq_text(tree, cast(int, scale))


def test_spatial_budgets_before_allocation() -> None:
    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    with pytest.raises(UnsupportedLoweringError, match="plaquette cells"):
        emit_bloq_text(tree, 1000000, max_plaquettes=10)
    with pytest.raises(UnsupportedLoweringError, match="qubits"):
        emit_bloq_text(tree, 1, max_qubits=1)


def test_concrete_tree_rejected() -> None:

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    concrete = LayerTree(
        StimMaterializer().materialize_layer(tree.construction_root), tree._observable_builder
    )
    with pytest.raises(UnsupportedLoweringError, match="concrete layer") as caught:
        emit_bloq_text(concrete, 1)
    assert caught.value.location is not None


@pytest.mark.parametrize("gate", ("R", "RX", "RY", "H", "M", "MX", "MY"))
def test_shared_operation_deduplication(gate) -> None:
    operation = (gate, ((-1, 1),))
    assert merge_moment([operation, operation], ()) == [operation]


def test_negative_measurement_mask_rejected() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        MeasurementRegistry().parity(-1)


def test_full_output_survives_backend_and_scale_changes() -> None:

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    root = tree.construction_root
    first = emit_bloq_text(tree, 1)
    tree.generate_circuit(2, detector_database=DetectorDatabase(), database_path=None)
    emit_bloq_text(tree, 2)
    assert emit_bloq_text(tree, 1) == first
    assert tree.construction_root is root
    assert "from blocks (0,0,0)" in first


def test_empty_repeat_traversal_budget() -> None:

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    empty = RepeatedLayer(tree.construction_root, LinearFunction(0, 0))
    many_empty = RepeatedLayer(empty, LinearFunction(0, 1000000))
    with pytest.raises(UnsupportedLoweringError, match="too many separators"):
        list(_timed_layers(many_empty, 1, 1))
