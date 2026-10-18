# ruff: noqa: PLC0415
import pytest
import stim

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tests.compile.lowering.bloq.flows_test import circuit_for, parity_indices, pauli
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.deltakit.flows import fragment_flows
from tqec.compile.lowering.deltakit.fragments import build_fragment
from tqec.compile.lowering.deltakit.layout import layout_moments
from tqec.compile.lowering.deltakit.tree import _layers


@pytest.mark.slow
@pytest.mark.timeout(120)
@pytest.mark.parametrize("case", ("memory_x", "memory_z", "junction", "hadamard"))
@pytest.mark.parametrize("convention", CONVENTIONS)
def test_native_declared_flows(case, convention) -> None:
    pytest.importorskip("deltakit_compile")
    from deltakit_compile.dialects import stabiliser as stab
    from deltakit_compile.frontend.circuit import QubitReg
    from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
    from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
    from deltakit_compile.passes.qstruct_circuit_to_stab import QStructCircuitToStabPass
    from deltakit_compile.passes.serialise_circuit import SerialiseCircuit
    from deltakit_compile.passes.split_gate_like_broadcast_ops import SplitGateLikeBroadcastOps
    from deltakit_compile.passes.stabiliser.verify_flows import VerifyFlows
    from xdsl.ir import Block
    from xdsl.transforms.canonicalize import CanonicalizePass

    tree = compile_block_graph(make_graph(case), CONVENTIONS[convention]).to_layer_tree()
    seen = set()
    for path, layer in _layers(tree.construction_root, 1):
        moments = layout_moments(layer, 1, True, path)
        signature = tuple(map(tuple, moments))
        if signature in seen:
            continue
        seen.add(signature)
        coords = sorted((q.x, q.y) for q in layer.qubits(1))
        circuit, _, _ = build_fragment("verify_fragment", coords, moments, True)
        builder = CircuitProgramBuilder()
        qubits = builder.declare_qubits(QubitReg(len(coords), qubit_locations=coords))
        builder.add_return(builder.call_circuit(circuit(qubits)))
        result = LogicalAssembler(LogicalAssemblerConfig(stabiliser_flow_config=None)).compile(
            builder.build_program()
        )
        context = LogicalAssembler.make_context()
        for stage in (
            SerialiseCircuit(),
            SplitGateLikeBroadcastOps(),
            QStructCircuitToStabPass(),
            CanonicalizePass(),
        ):
            stage.apply(context, result.module)
        result.module.verify()
        # A fragment has arbitrary incoming Paulis, not a freshly allocated state.
        # Give the native verifier an explicit state argument for this local contract.
        checked = 0
        for op in result.module.walk():
            if not isinstance(op, stab.CircuitOp):
                continue
            assert isinstance(op.input.type, stab.StateType)
            concrete = stab.ConcreteFlowArrayAttr.get(op)
            if concrete is None:
                continue
            # Verify each declared relation independently: redundant creation
            # relations are legal concrete contracts but cannot share a stab
            # output-state index in a single native FlowAttr array.
            # Native propagation recomputes the whole slice for each relation.
            # Sample both boundary directions here; the signed oracle below
            # checks every relation on every distinct fragment.
            representatives = {}
            for flow in concrete.flows:
                representatives.setdefault((flow.input_state.is_identity(), flow.is_plus), flow)
            for f in representatives.values():
                input_type = stab.StateType(
                    len(coords),
                    op.input.type.qubit_type,
                    [] if f.input_state.is_identity() else [f.input_state],
                )
                output_type = stab.StateType(
                    len(coords),
                    op.input.type.qubit_type,
                    [] if f.output_state.is_identity() else [f.output_state],
                )
                scope = Block(arg_types=[input_type])
                body = op.body.clone()
                old_yield = body.block.last_op
                assert isinstance(old_yield, stab.YieldOp)
                body.block.insert_op_before(
                    stab.YieldOp(list(old_yield.arguments), list(old_yield.arguments)), old_yield
                )
                body.block.erase_op(old_yield)
                local = stab.CircuitOp(
                    scope.args[0],
                    output_type,
                    input_args=[],
                    body=body,
                    flows=[
                        stab.FlowAttr.from_states(
                            f.sign,
                            [i - 1 for i in f.measurement_indices],
                            f.input_state,
                            f.output_state,
                            input_state_context=input_type,
                            output_state_context=output_type,
                        )
                    ],
                )
                scope.add_op(local)
                local.verify()
                VerifyFlows.check_circuit_op(local)
                checked += 1
        assert checked

        reference = circuit_for(moments, coords)
        creation, destruction = fragment_flows(moments, coords)
        for family, direction in ((creation, "output"), (destruction, "input")):
            for x, z, records, sign in family:
                assert reference.has_flow(
                    stim.Flow(
                        **{direction: pauli(x, z, sign, len(coords))},
                        measurements=parity_indices(records),
                    )
                )
