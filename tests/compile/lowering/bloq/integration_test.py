import pytest

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tests.compile.lowering.bloq.physical_test import physical_moments
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq import lower_to_bloq
from tqec.computation.block_graph import BlockGraph
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def checks(circuit):
    coords = circuit.get_final_qubit_coordinates()
    records = []
    detectors = []
    observables = {}
    tick = 0
    for instruction in circuit.flattened():
        if instruction.name == "TICK":
            tick += 1
        elif instruction.name in {"M", "MX", "MY"}:
            records.extend((tick, tuple(coords[q.value])) for q in instruction.targets_copy())
        elif instruction.name in {"DETECTOR", "OBSERVABLE_INCLUDE"}:
            parity = set()
            for target in instruction.targets_copy():
                parity.symmetric_difference_update([records[target.value]])
            if instruction.name == "DETECTOR":
                detectors.append(parity)
            else:
                index = int(instruction.gate_args_copy()[0])
                observables.setdefault(index, set()).symmetric_difference_update(parity)
    return detectors, observables


def rank(rows):
    pivots = {}
    for row in rows:
        value = set(row)
        while value:
            pivot = max(value)
            if pivot not in pivots:
                pivots[pivot] = value
                break
            value.symmetric_difference_update(pivots[pivot])
    return len(pivots)


@pytest.mark.parametrize(
    "case", ("memory_x", "memory_z", "temporal", "spatial", "cnot", "junction", "hadamard")
)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_complete_qec_differential(case, convention, k) -> None:
    bloq = pytest.importorskip("bloq")
    compiled = compile_block_graph(make_graph(case), CONVENTIONS[convention])
    actual = bloq.emit_stim(lower_to_bloq(compiled.to_layer_tree(), k))
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
    bloq = pytest.importorskip("bloq")
    compiled = compile_block_graph(
        make_graph("spatial").shift_by(dx=-3, dy=-2, dz=4), CONVENTIONS[convention]
    )
    actual = bloq.emit_stim(lower_to_bloq(compiled.to_layer_tree(), 1))
    expected = compiled.generate_stim_circuit(
        1, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert rank(detectors) == rank(reference) == rank(detectors + reference)


def test_unrelated_temporal_hadamard() -> None:

    bloq = pytest.importorskip("bloq")
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
    actual = bloq.emit_stim(lower_to_bloq(tree, 1))
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


@pytest.mark.parametrize(
    "case,convention",
    (
        ("junction", "boundary"),
        ("hadamard", "bulk"),
        ("memory_z", "diagonal"),
    ),
)
def test_original_measurement_schedules(case, convention) -> None:
    bloq = pytest.importorskip("bloq")
    compiled = compile_block_graph(make_graph(case), CONVENTIONS[convention])
    gates_only = case == "junction"
    if gates_only:
        with pytest.raises(UnsupportedLoweringError, match="enable rescheduling"):
            lower_to_bloq(compiled.to_layer_tree(), 1, reschedule_measurements=False)
    actual = bloq.emit_stim(
        lower_to_bloq(
            compiled.to_layer_tree(), 1, reschedule_measurements=False, gates_only=gates_only
        )
    )
    expected = compiled.generate_stim_circuit(
        1,
        detector_database=DetectorDatabase(),
        database_path=None,
        reschedule_measurements=False,
    )
    assert physical_moments(actual) == physical_moments(expected)
    if gates_only:
        return
    detectors, observables = checks(actual)
    reference, ref_observables = checks(expected)
    assert observables == ref_observables
    assert rank(detectors) == rank(reference) == rank(detectors + reference)
    actual.detector_error_model()
