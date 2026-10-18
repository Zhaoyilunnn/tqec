# ruff: noqa: PLC0415
from dataclasses import fields

import pytest
import stim

from tests.compile.lowering.bloq.flows_test import parity_indices, pauli
from tests.compile.lowering.bloq.physical_test import physical_moments
from tqec.compile.lowering.deltakit.extended import extended_operations
from tqec.compile.lowering.deltakit.flows import fragment_flows
from tqec.compile.lowering.deltakit.realignment import realignment_operations
from tqec.compile.lowering.deltakit.rpng import rpng_operations
from tqec.compile.lowering.stim.materializer import StimMaterializer
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.extended_specs import ExtendedSpecCollection
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.spec import (
    DataQubitOperations,
    ExtendedPlaquetteDataQubitsOperations,
    RealignmentPlaquetteSpec,
    RPNGPlaquetteSpec,
)
from tqec.utils.enums import Basis, Orientation


def verify(spec, operations) -> None:
    moments = [operations.get(t, []) for t in range(max(operations) + 1)]
    qubits = sorted({q for moment in moments for _, targets in moment for q in targets})
    pytest.importorskip("deltakit_compile")
    from deltakit_compile.frontend.circuit import QubitReg
    from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
    from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
    from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

    from tqec.compile.lowering.deltakit.fragments import build_fragment

    fragment, _, _ = build_fragment("local", qubits, moments, False)
    builder = CircuitProgramBuilder()
    register = builder.declare_qubits(QubitReg(len(qubits), qubit_locations=qubits))
    returned = builder.call_circuit(fragment(register))
    if returned is not None:
        builder.add_return(returned)
    result = LogicalAssembler(
        LogicalAssemblerConfig(
            stabiliser_flow_config=None, export_config=StimExportPipelineConfig()
        )
    ).compile(builder.build_program())
    result.module.verify()
    actual = stim.Circuit(result.program)
    expected = StimMaterializer().materialize_plaquette(spec).circuit.get_circuit()
    assert physical_moments(actual) == physical_moments(expected)
    # Native export groups measurements by basis within a moment. Resolve
    # records by physical identity instead of assuming the original list order.
    source_records = [
        q for moment in moments for gate, targets in moment if gate.startswith("M") for q in targets
    ]
    coordinates = actual.get_final_qubit_coordinates()
    exported_records = [
        tuple(coordinates[target.value])
        for instruction in actual
        if isinstance(instruction, stim.CircuitInstruction)
        and instruction.name in {"M", "MX", "MY"}
        for target in instruction.targets_copy()
    ]
    record_map = {i: exported_records.index(q) for i, q in enumerate(source_records)}
    creation, destruction = fragment_flows(moments, qubits)
    for flows, boundary in ((creation, "output"), (destruction, "input")):
        for x, z, records, sign in flows:
            assert actual.has_flow(
                stim.Flow(
                    **{boundary: pauli(x, z, sign, len(qubits))},
                    measurements=[record_map[i] for i in parity_indices(records)],
                )
            )


@pytest.mark.parametrize("orientation", tuple(Orientation))
@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("basis", tuple(Basis))
@pytest.mark.parametrize("boundary", (None, Basis.X, Basis.Z))
def test_extended_shapes(orientation, reverse, basis, boundary) -> None:
    specs = ExtendedSpecCollection.from_basis(
        basis,
        boundary,
        boundary,
        reverse,
        orientation=orientation,
        data_operations=ExtendedPlaquetteDataQubitsOperations(
            DataQubitOperations(boundary, boundary), DataQubitOperations(boundary, boundary)
        ),
    )
    for field in fields(specs):
        for half in ("top", "bottom"):
            spec = getattr(getattr(specs, field.name), half)
            verify(spec, extended_operations(spec))


@pytest.mark.parametrize("orientation", tuple(Orientation))
@pytest.mark.parametrize("basis", tuple(Basis))
@pytest.mark.parametrize("reset", tuple(Basis))
@pytest.mark.parametrize("measurement", tuple(Basis))
def test_realignment_projections(orientation, basis, reset, measurement) -> None:
    spec = RealignmentPlaquetteSpec(basis, orientation, reset, measurement)
    for boundary in (None, *PlaquetteOrientation):
        projected = spec if boundary is None else spec.project_on_boundary(boundary)
        verify(projected, realignment_operations(projected))


@pytest.mark.parametrize(
    "description",
    (
        "-z1- -z3- -z2- -z4-",
        "zx1z ---- zx3z ----",
        "-x5h -z2z -x3x hz1-",
        "-y1- -y2- -y3- -y4-",
        "---- ---- ---- ----",
    ),
)
@pytest.mark.parametrize("schedule", (6, 8))
def test_rpng_schedule_and_bases(description, schedule) -> None:
    spec = RPNGPlaquetteSpec(RPNGDescription.from_string(description), schedule)
    verify(spec, rpng_operations(spec))
