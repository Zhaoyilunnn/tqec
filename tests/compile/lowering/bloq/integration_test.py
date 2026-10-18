import pytest

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tests.compile.lowering.bloq.physical_test import physical_moments
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.bloq import lower_to_bloq
from tqec.utils.noise_model import NoiseModel


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
