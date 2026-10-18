import json
from pathlib import Path

import pytest
import stim

from tests.experiment.cases import CASES, CONVENTIONS, make_graph
from tests.experiment.oracles import digest, physical
from tqec.circuit.native import compile_module
from tqec.compile.compile import compile_block_graph


@pytest.mark.timeout(120)
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("convention", CONVENTIONS)
@pytest.mark.parametrize("k", (1, 2))
def test_native_physical(case, convention, k):
    tree = compile_block_graph(make_graph(case), CONVENTIONS[convention]).to_layer_tree()
    module = tree.get_native_module(k)
    module.verify()
    actual = stim.Circuit(compile_module(module, export="stim").program)
    expected = json.loads(Path("tests/experiment/baseline.json").read_text())[
        f"{convention}-{case}-{k}"
    ]
    assert digest(physical(actual)) == expected["physical"]
    assert actual.num_measurements == expected["measurements"]
    assert (
        digest(sorted(actual.get_final_qubit_coordinates().values())) == expected["coordinate_set"]
    )
