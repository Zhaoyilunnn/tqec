# ruff: noqa: PLC0415
import pytest
import stim

from tests.compile.decoupling_baseline_test import CASES, CONVENTIONS, make_graph
from tests.compile.lowering.bloq.integration_test import checks, rank
from tests.compile.lowering.bloq.physical_test import physical_moments
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.deltakit import compile_to_deltakit
from tqec.computation.block_graph import BlockGraph
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


@pytest.mark.timeout(120)
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_complete_qec(case, convention, k) -> None:
    pytest.importorskip("deltakit_compile")
    compiled = compile_block_graph(make_graph(case), CONVENTIONS[convention])
    actual = stim.Circuit(compile_to_deltakit(compiled.to_layer_tree(), k, export="stim").program)
    expected = compiled.generate_stim_circuit(
        k, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert rank(detectors) == rank(reference) == rank(detectors + reference)
    actual.detector_error_model()
    sampled, logical = actual.compile_detector_sampler(seed=0).sample(32, separate_observables=True)
    assert not sampled.any()
    assert not logical.any()
    if case in {"memory_x", "memory_z", "spatial"}:
        noisy = NoiseModel.uniform_depolarizing(0.001).noisy_circuit(actual)
        assert len(noisy.shortest_graphlike_error()) == 2 * k + 1


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_shifted_negative_layout(convention) -> None:
    pytest.importorskip("deltakit_compile")
    compiled = compile_block_graph(
        make_graph("spatial").shift_by(dx=-3, dy=-2, dz=4), CONVENTIONS[convention]
    )
    actual = stim.Circuit(compile_to_deltakit(compiled.to_layer_tree(), 1, export="stim").program)
    expected = compiled.generate_stim_circuit(
        1, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert rank(detectors) == rank(reference) == rank(detectors + reference)


def test_unrelated_temporal_hadamard() -> None:

    pytest.importorskip("deltakit_compile")
    graph = BlockGraph()
    for pos in ((0, 0, 0), (1, 0, 0), (0, 0, 1)):
        graph.add_cube(Position3D(*pos), "ZXZ")
    graph.add_pipe(Position3D(0, 0, 0), Position3D(1, 0, 0))
    graph.add_pipe(Position3D(0, 0, 0), Position3D(0, 0, 1))
    (observable,) = graph.find_correlation_surfaces()
    graph.add_cube(Position3D(3, 0, 0), "ZXZ")
    graph.add_cube(Position3D(3, 0, 1), "XZX")
    graph.add_pipe(Position3D(3, 0, 0), Position3D(3, 0, 1))
    compiled = compile_block_graph(graph, observables=[observable])
    tree = compiled.to_layer_tree()
    actual = stim.Circuit(compile_to_deltakit(tree, 1, export="stim").program)
    expected = compiled.generate_stim_circuit(
        1, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert sum(map(len, observables.values())) == 7
    assert rank(detectors) == rank(reference) == rank(detectors + reference)
    actual.detector_error_model()


@pytest.mark.timeout(240)
@pytest.mark.parametrize("case", ("move_rotation", "three_cnots", "disjoint"))
def test_additional_compositions(case) -> None:
    pytest.importorskip("deltakit_compile")
    if case == "disjoint":
        graph = BlockGraph()
        for x, kind in ((-2, "XZZ"), (2, "XZX")):
            first = graph.add_cube(Position3D(x, 0, 0), kind)
            second = graph.add_cube(Position3D(x, 0, 1), kind)
            graph.add_pipe(first, second)
    else:
        from tqec.gallery.move_rotation import move_rotation
        from tqec.gallery.three_cnots import three_cnots
        from tqec.utils.enums import Basis

        graph = {"move_rotation": move_rotation, "three_cnots": three_cnots}[case](Basis.Z)
    compiled = compile_block_graph(graph)
    actual = stim.Circuit(compile_to_deltakit(compiled.to_layer_tree(), 1, export="stim").program)
    expected = compiled.generate_stim_circuit(
        1, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert rank(detectors) == rank(reference) == rank(detectors + reference)
    actual.detector_error_model()
