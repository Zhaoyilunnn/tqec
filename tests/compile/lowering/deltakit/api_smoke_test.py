# ruff: noqa: PLC0415
import pytest


def make_program(explicit=False):
    pytest.importorskip("deltakit_compile")
    from deltakit_compile.frontend.circuit import CircuitBuilder, ParallelAlignment, QubitReg
    from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder

    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))
    with builder.parallel(ParallelAlignment.LOCKSTEP) as parallel:
        with parallel():
            builder.gate("RZ", qubits[0])
        with parallel():
            builder.gate("RZ", qubits[1])
    builder.gate("CX", [qubits[0], qubits[1]])
    result = builder.measure("Z", qubits[1])
    builder.add_return(result)
    if explicit:
        builder.detector([result], (1.0, 0.0, 0.0))
    fragment = builder.build("tqec_smoke")
    program = CircuitProgramBuilder()
    placed = program.declare_qubits(QubitReg(2, qubit_locations=[(0, 0), (1, 0)]))
    program.add_return(program.call_circuit(fragment(placed)))
    return program.build_program()


@pytest.mark.parametrize("explicit", (False, True))
def test_native_ir_and_export(explicit) -> None:
    pytest.importorskip("deltakit_compile")
    from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
    from deltakit_compile.passes.logical_assembly.pipeline import PhysicalCircuitIRExportConfig
    from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig
    from xdsl.dialects.builtin import ModuleOp

    for export in (PhysicalCircuitIRExportConfig(), StimExportPipelineConfig()):
        program = make_program(explicit)
        program.module.verify()
        result = LogicalAssembler(
            LogicalAssemblerConfig(export_config=export, stabiliser_flow_config=None)
        ).compile(program)
        assert isinstance(result.module, ModuleOp)
        result.module.verify()
        assert isinstance(result.program, str)
        assert result.auxiliary_outputs is not None
        if isinstance(export, PhysicalCircuitIRExportConfig):
            names = {op.name for op in result.module.walk()}
            assert {"qref.reset", "qref.gate", "qref.measure"} <= names
        else:
            assert "CNOT 0 1" in result.program
            assert "M 1" in result.program
            assert ("DETECTOR" in result.program) == explicit
