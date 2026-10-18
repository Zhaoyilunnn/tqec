import pytest

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.bloq import emit_bloq_text, lower_to_bloq


def physical_moments(circuit):
    coordinates = circuit.get_final_qubit_coordinates()
    result = [[]]
    for instruction in circuit.flattened():
        if instruction.name == "TICK":
            result.append([])
        elif instruction.name not in {
            "QUBIT_COORDS",
            "SHIFT_COORDS",
            "DETECTOR",
            "OBSERVABLE_INCLUDE",
        }:
            for group in instruction.target_groups():
                result[-1].append(
                    (instruction.name, tuple(tuple(coordinates[q.value]) for q in group))
                )
    while result and not result[-1]:
        result.pop()
    return [sorted(moment) for moment in result]


@pytest.mark.parametrize(
    "case", ("memory_x", "memory_z", "temporal", "spatial", "cnot", "junction", "hadamard")
)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_physical_differential(case, convention, k) -> None:
    bloq = pytest.importorskip("bloq")
    compiled = compile_block_graph(make_graph(case), CONVENTIONS[convention])
    tree = compiled.to_layer_tree()
    text = emit_bloq_text(tree, k, gates_only=True)
    program = lower_to_bloq(tree, k, gates_only=True)
    actual = bloq.emit_stim(program)
    expected = compiled.generate_stim_circuit(
        k, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    assert actual.num_measurements == expected.num_measurements
    tree.generate_circuit(k, detector_database=DetectorDatabase(), database_path=None)
    assert emit_bloq_text(tree, k, gates_only=True) == text
