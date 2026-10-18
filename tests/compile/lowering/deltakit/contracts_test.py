# ruff: noqa: PLC0415
import subprocess
import sys
from typing import cast

import pytest
import stim

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tests.compile.lowering.bloq.integration_test import checks, rank
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.deltakit import DeltakitOptions, compile_to_deltakit


def test_optional_dependency() -> None:
    script = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] == 'deltakit_compile':
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, Block())
import tqec
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.bloq import emit_bloq_text
from tqec.compile.lowering.deltakit import lower_to_deltakit_ir
from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import Position3D
from tqec.utils.exceptions import TQECError
g = BlockGraph()
g.add_cube(Position3D(0, 0, 0), 'XZZ')
t = compile_block_graph(g).to_layer_tree()
assert 'observable' in emit_bloq_text(t, 1)
try:
    lower_to_deltakit_ir(t, 1)
except TQECError as e:
    assert 'Install the pinned' in str(e)
else:
    raise AssertionError('missing dependency ignored')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_direct_native_producer() -> None:
    pytest.importorskip("deltakit_compile")
    script = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if (fullname.split('.')[0] in {'stim', 'tqecd', 'bloq'}
            or fullname.startswith(('tqec.compile.lowering.stim', 'tqec.compile.lowering.bloq'))):
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, Block())
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.deltakit import lower_to_deltakit_ir
from tqec.computation.block_graph import BlockGraph
from tqec.utils.position import Position3D
g = BlockGraph()
g.add_cube(Position3D(0, 0, 0), 'XZZ')
t = compile_block_graph(g).to_layer_tree()
lower_to_deltakit_ir(t, 1).verify()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_explicit_modes_and_budgets() -> None:
    pytest.importorskip("deltakit_compile")
    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    for k in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="positive integer"):
            compile_to_deltakit(tree, cast(int, k))
    for options in (
        DeltakitOptions(max_unrolled_rounds=1),
        DeltakitOptions(max_plaquettes=1),
        DeltakitOptions(max_qubits=1),
        DeltakitOptions(strict_schedule=False),
        DeltakitOptions(annotation_mode="none"),
        DeltakitOptions(annotation_mode="auto"),
    ):
        with pytest.raises(UnsupportedLoweringError):
            compile_to_deltakit(tree, 1, options=options)


@pytest.mark.parametrize("case", ("memory_x", "memory_z"))
@pytest.mark.parametrize("k", (1, 2))
def test_auto_is_deterministic_but_experimental(case, k) -> None:
    pytest.importorskip("deltakit_compile")
    compiled = compile_block_graph(make_graph(case))
    result = compile_to_deltakit(
        compiled.to_layer_tree(),
        k,
        export="stim",
        options=DeltakitOptions(annotation_mode="auto", include_observables=False),
    )
    actual = stim.Circuit(result.program)
    expected = compiled.generate_stim_circuit(
        k, detector_database=DetectorDatabase(), database_path=None
    )
    detectors, observables = checks(actual)
    reference, _ = checks(expected)
    assert not observables
    actual.detector_error_model()
    sampled, _ = actual.compile_detector_sampler(seed=0).sample(32, separate_observables=True)
    assert not sampled.any()
    # The native finder includes the logical readout constraint. Do not claim
    # these checks are an interchangeable QEC detector basis.
    assert rank(detectors) == rank(reference) + 1 == rank(detectors + reference)


def test_same_tree_across_three_backends() -> None:
    pytest.importorskip("deltakit_compile")
    from tqec.compile.lowering.bloq import emit_bloq_text

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    root = tree.construction_root
    first = compile_to_deltakit(tree, 1, export="stim").program
    bloq = emit_bloq_text(tree, 1)
    tree.generate_circuit(2, detector_database=DetectorDatabase(), database_path=None)
    compile_to_deltakit(tree, 2).module.verify()
    assert compile_to_deltakit(tree, 1, export="stim").program == first
    assert emit_bloq_text(tree, 1) == bloq
    assert tree.construction_root is root


def test_concrete_layer_rejected() -> None:
    pytest.importorskip("deltakit_compile")
    from tqec.compile.lowering.stim.materializer import StimMaterializer
    from tqec.compile.tree.tree import LayerTree

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    concrete = LayerTree(
        StimMaterializer().materialize_layer(tree.construction_root), tree._observable_builder
    )
    with pytest.raises(UnsupportedLoweringError, match="concrete layer") as caught:
        compile_to_deltakit(concrete, 1)
    assert caught.value.location is not None


def test_unrescheduled_junction_requires_physical_only() -> None:
    pytest.importorskip("deltakit_compile")
    from tests.compile.lowering.bloq.physical_test import physical_moments

    compiled = compile_block_graph(make_graph("junction"), CONVENTIONS["boundary"])
    with pytest.raises(UnsupportedLoweringError, match="rescheduling"):
        compile_to_deltakit(
            compiled.to_layer_tree(), 1, options=DeltakitOptions(reschedule_measurements=False)
        )
    actual = stim.Circuit(
        compile_to_deltakit(
            compiled.to_layer_tree(),
            1,
            export="stim",
            options=DeltakitOptions(
                annotation_mode="none", include_observables=False, reschedule_measurements=False
            ),
        ).program
    )
    expected = compiled.generate_stim_circuit(
        1, reschedule_measurements=False, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)


def test_empty_repeat_traversal_budget() -> None:
    from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
    from tqec.compile.lowering.deltakit.tree import _timed_layers
    from tqec.utils.scale import LinearFunction

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    empty = RepeatedLayer(tree.construction_root, LinearFunction(0, 0))
    many_empty = RepeatedLayer(empty, LinearFunction(0, 1000000))
    with pytest.raises(UnsupportedLoweringError, match="too many separators"):
        list(_timed_layers(many_empty, 1, 1))


def test_native_fragment_reuse() -> None:
    pytest.importorskip("deltakit_compile")
    import json

    from tqec.compile.lowering.deltakit import build_deltakit_program

    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    program = build_deltakit_program(tree, 2)
    provenance = json.loads(program.module.attributes["tqec.provenance"].data)
    assert provenance["templates"] < provenance["rounds"]
    assert provenance["measurements"] > 0
    program.module.verify()
