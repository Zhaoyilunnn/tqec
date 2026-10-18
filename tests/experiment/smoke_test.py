# ruff: noqa: PLC0415
"""Boundary interoperability controls, never used by the native producer."""

from pathlib import Path

import pytest
import stim

from tests.experiment.oracles import physical


@pytest.mark.parametrize("basis", ("x", "z"))
@pytest.mark.parametrize("k", (1, 2))
def test_import_export_control(basis, k):
    import deltakit_stim
    from deltakit_compile.frontend.deltakit_stim.io import (
        deltakit_stim_circuit_to_physical_circuit_ir,
        physical_circuit_ir_to_deltakit_stim_circuit,
    )

    path = Path(__file__).with_name("fixtures") / f"memory_{basis}-{k}.stim"
    expected = stim.Circuit(path.read_text())
    module = deltakit_stim_circuit_to_physical_circuit_ir(deltakit_stim.Circuit(str(expected)))
    module.verify()
    actual = stim.Circuit(str(physical_circuit_ir_to_deltakit_stim_circuit(module)))
    assert physical(actual) == physical(expected)
    assert actual.num_measurements == expected.num_measurements
    assert actual.num_observables == expected.num_observables
    actual.detector_error_model()
