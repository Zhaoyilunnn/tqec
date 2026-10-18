import pytest
import stim

from tests.compile.decoupling_baseline_test import CASES, CONVENTIONS, make_graph
from tests.compile.lowering.bloq.physical_test import physical_moments
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.deltakit import DeltakitOptions, compile_to_deltakit


@pytest.mark.timeout(120)
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_physical_schedule(case, convention, k) -> None:
    pytest.importorskip("deltakit_compile")
    compiled = compile_block_graph(make_graph(case), CONVENTIONS[convention])
    tree = compiled.to_layer_tree()
    result = compile_to_deltakit(
        tree,
        k,
        options=DeltakitOptions(annotation_mode="none", include_observables=False),
        export="stim",
    )
    actual = stim.Circuit(result.program)
    expected = compiled.generate_stim_circuit(
        k, detector_database=DetectorDatabase(), database_path=None
    )
    assert physical_moments(actual) == physical_moments(expected)
    assert actual.num_measurements == expected.num_measurements
    assert set(map(tuple, actual.get_final_qubit_coordinates().values())) == set(
        map(tuple, expected.get_final_qubit_coordinates().values())
    )
