from pathlib import Path

import pytest
import stim

from tests.experiment.cases import make_graph
from tests.experiment.oracles import canonical_space, checks, rank
from tqec.circuit.native import compile_module
from tqec.compile.compile import compile_block_graph


@pytest.mark.timeout(120)
@pytest.mark.parametrize("case", ("memory_x", "memory_z"))
@pytest.mark.parametrize("k", (1, 2))
def test_native_auto_finding_is_experimental(case, k):
    tree = compile_block_graph(make_graph(case)).to_layer_tree()
    module = tree.get_native_module(k, annotation_mode="auto")
    actual = stim.Circuit(compile_module(module, export="stim").program)
    actual.detector_error_model()
    detectors, obs = checks(actual)
    assert not obs
    # A memory has (d*d - 1)*d independent syndrome checks. Auto also
    # includes the deterministic logical readout constraint.
    distance = 2 * k + 1
    assert rank(detectors) == (distance * distance - 1) * distance + 1

    reference = stim.Circuit(
        Path(__file__).with_name("fixtures").joinpath(f"{case}-{k}.stim").read_text()
    )
    expected_checks, expected_obs = checks(reference)
    assert canonical_space(detectors) == canonical_space([*expected_checks, *expected_obs.values()])
