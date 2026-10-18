"""Small helpers over Deltakit operations; no local instruction representation."""

from deltakit_compile.dialects import qcore, qref, qstruct
from deltakit_compile.dialects.stim import TickAnnotationOp
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.logical_assembly.pipeline import PhysicalCircuitIRExportConfig
from deltakit_compile.passes.stabiliser.pipeline import StabiliserFlowPipelineConfig
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Region

from tqec.utils.exceptions import TQECError


def gate_name(op):
    """Read the physical name of one supported native operation."""
    if isinstance(op, qref.ResetOp):
        return "R" if op.basis.data.value.upper() == "Z" else "R" + op.basis.data.value.upper()
    if isinstance(op, qref.MeasureOp):
        if op.noise.value.data != 0 or any(len(group) != 1 for group in op.qubit_operand_groups):
            raise TQECError("Noisy and multi-qubit native measurements are unsupported.")
        if len({tuple(str(p) for p in group) for group in op.paulis}) != 1:
            raise TQECError("Mixed-basis native broadcasts must be split explicitly.")
        basis = op.paulis.data[0].data[0].data.value.upper()
        return "M" if basis == "Z" else "M" + basis
    if isinstance(op, qref.GateOp):
        for name in ("H", "CX", "CY", "CZ", "X", "Y", "Z"):
            if isinstance(op.gate, getattr(qcore, name + "GateAttr")):
                return name
    raise TQECError(f"Unsupported native operation: {op.name}")


def make_operation(name, qubits):
    """Create a native operation immediately from construction arguments."""
    name = {"RZ": "R", "MZ": "M"}.get(name, name)
    if name in {"R", "RX", "RY"}:
        return qref.ResetOp("Z" if name == "R" else name[-1], qubits)
    if name in {"M", "MX", "MY"}:
        return qref.MeasureOp("Z" if name == "M" else name[-1], qubits)
    if name in {"H", "CX", "CY", "CZ", "X", "Y", "Z"}:
        return qref.GateOp(getattr(qcore, name + "GateAttr")(), qubits)
    raise TQECError(f"Unsupported direct Deltakit gate: {name}")


def assemble(moments, qubit_map, annotate=None):
    """Clone native moments into one scoped physical circuit with explicit ticks."""
    indices = list(qubit_map.indices)
    allocation = qcore.AllocQubitOp(
        [qcore.QubitType() for _ in indices],
        coordinates=[(qubit_map.i2q[i].x, qubit_map.i2q[i].y) for i in indices],
        ids=indices,
    )
    body = Block(arg_types=[qcore.QubitType() for _ in indices])
    global_qubits = dict(zip(indices, body.args))
    records = []
    for moment in moments:
        if moment is None or moment.is_empty:
            body.add_op(TickAnnotationOp())
            continue
        branches = []
        results = []
        mapping = {arg: global_qubits[i] for i, arg in moment.qubit_ssa.items()}
        for op in moment.instructions:
            cloned = op.clone(value_mapper=mapping)
            branch = Block([cloned, qstruct.YieldOp(*cloned.results)])
            branches.append(branch)
            results.extend(cloned.result_types)
        parallel = qstruct.ParallelOp(results, branches)
        body.add_op(parallel)
        records.extend(parallel.results)
    if annotate is not None:
        annotate(body, records)
    body.add_op(qstruct.YieldOp(*body.args, *records))
    circuit = qstruct.CircuitOp(
        allocation.results,
        [arg.type for arg in body.args] + [v.type for v in records],
        Region(body),
    )
    module = ModuleOp([allocation, circuit, qstruct.OutputOp(circuit.results[len(indices) :])])
    module.verify()
    return module


def compile_module(module, export="physical-ir", auto=False):
    """Run native passes, optionally exporting only at this boundary."""
    result = LogicalAssembler(
        LogicalAssemblerConfig(
            export_config=StimExportPipelineConfig()
            if export == "stim"
            else PhysicalCircuitIRExportConfig(),
            stabiliser_flow_config=StabiliserFlowPipelineConfig() if auto else None,
        )
    ).compile(module)
    result.module.verify()
    return result
