from copy import deepcopy

import pytest
from deltakit_compile.dialects import qref

from tqec.circuit.moment import Moment, MultipleOperationsOnSameQubitError
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit


def test_clone_remap_measurement_and_scope():
    moment = Moment()
    moment.append('MX', [7])
    cloned = moment.with_mapped_qubit_indices({7: 2})
    old, = moment.instructions
    new, = cloned.instructions
    assert isinstance(new, qref.MeasureOp)
    assert new.results[0] is not old.results[0]
    assert new.operands[0] is cloned.qubit_ssa[2]
    circuit = ScheduledCircuit([cloned], [2], QubitMap({2: GridQubit(-1, 1)}))
    circuit.get_native_module().verify()
    exported = circuit.get_circuit()
    assert exported.num_ticks == 2
    assert exported.num_measurements == 1
    assert deepcopy(moment) == moment


def test_merge_filter_conflicts():
    first, second = Moment(), Moment()
    first.append('RX', [0])
    second.append('RZ', [1])
    merged = first + second
    assert merged.qubits_indices == {0, 1}
    assert merged.filter_by_qubits([0]).qubits_indices == {0}
    with pytest.raises(MultipleOperationsOnSameQubitError):
        merged.append('H', [0])
    with pytest.raises(MultipleOperationsOnSameQubitError):
        first + first
