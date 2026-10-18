import pytest
import stim

from tests.compile.decoupling_baseline_test import CONVENTIONS, make_graph
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.bloq.emitter import _layers
from tqec.compile.lowering.bloq.flows import closed_relations, fragment_flows
from tqec.compile.lowering.bloq.layout import layout_moments
from tqec.compile.lowering.bloq.rpng import rpng_operations
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.spec import RPNGPlaquetteSpec


def circuit_for(moments, qubits):
    circuit = stim.Circuit()
    lookup = {q: i for i, q in enumerate(qubits)}
    for t, moment in enumerate(moments):
        if t:
            circuit.append("TICK", [])
        for gate, targets in moment:
            circuit.append(gate, [lookup[q] for q in targets])
    return circuit


def pauli(x, z, sign, n):
    result = stim.PauliString(n)
    for i in range(n):
        result[i] = "IXZY"[((x >> i) & 1) + 2 * ((z >> i) & 1)]
    result.sign = -1 if sign else 1
    return result


def parity_indices(bits):
    return [i for i in range(bits.bit_length()) if bits >> i & 1]


def test_generated_flow_relations() -> None:
    for description in (
        "-x1- -x2- -x3- -x4-",
        "xx1- xx2- xx3- xx4-",
        "-z1z -z3z -z2z -z4z",
        "-y1- -y2- -y3- -y4-",
    ):
        spec = RPNGPlaquetteSpec(RPNGDescription.from_string(description))
        operations = rpng_operations(spec)
        moments = [operations.get(t, []) for t in range(max(operations) + 1)]
        qubits = sorted({q for moment in moments for _, targets in moment for q in targets})
        circuit = circuit_for(moments, qubits)
        creation, destruction = fragment_flows(moments, qubits)
        for x, z, records, sign in creation:
            assert circuit.has_flow(
                stim.Flow(
                    output=pauli(x, z, sign, len(qubits)), measurements=parity_indices(records)
                )
            )
        for x, z, records, sign in destruction:
            assert circuit.has_flow(
                stim.Flow(
                    input=pauli(x, z, sign, len(qubits)), measurements=parity_indices(records)
                )
            )
        for family in (creation, destruction):
            for records, sign in closed_relations(family, len(qubits)):
                assert circuit.has_flow(
                    stim.Flow(
                        output=pauli(0, 0, sign, len(qubits)), measurements=parity_indices(records)
                    )
                )


@pytest.mark.parametrize("case", ("memory_x", "memory_z", "junction", "hadamard"))
@pytest.mark.parametrize("convention", CONVENTIONS)
def test_layout_boundary_flows(case, convention) -> None:
    tree = compile_block_graph(make_graph(case), CONVENTIONS[convention]).to_layer_tree()
    for path, layer in _layers(tree.construction_root, 1):
        moments = layout_moments(layer, 1, True, path)
        qubits = sorted({q for moment in moments for _, targets in moment for q in targets})
        circuit = circuit_for(moments, qubits)
        creation, destruction = fragment_flows(moments, qubits)
        for flows, boundary in ((creation, "output"), (destruction, "input")):
            for x, z, records, sign in flows:
                assert circuit.has_flow(
                    stim.Flow(
                        **{boundary: pauli(x, z, sign, len(qubits))},
                        measurements=parity_indices(records),
                    )
                )
