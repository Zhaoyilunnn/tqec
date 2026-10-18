import json
from pathlib import Path

import pytest

from tests.experiment.cases import CASES, CONVENTIONS, make_graph
from tests.experiment.oracles import canonical_space, checks, digest, physical
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase


@pytest.mark.timeout(240)
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_legacy_detector_equivalence(case, convention, k):
    expected = json.loads(Path("tests/experiment/baseline.json").read_text())[
        f"{convention}-{case}-{k}"
    ]
    tree = compile_block_graph(make_graph(case), CONVENTIONS[convention]).to_layer_tree()
    actual = tree.generate_circuit(k, detector_database=DetectorDatabase(), database_path=None)
    assert digest(physical(actual)) == expected["physical"]
    ds, obs = checks(actual)
    assert digest({i: sorted(v) for i, v in obs.items()}) == expected["observables"]
    assert digest(canonical_space(ds)) == expected["detector_space"]
    actual.detector_error_model()
