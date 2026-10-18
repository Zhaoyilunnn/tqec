# ruff: noqa: PLC0415
from copy import deepcopy

import pytest
from deltakit_compile.dialects import qref

from tqec.circuit.moment import Moment, MultipleOperationsOnSameQubitError
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit


def test_clone_remap_measurement_and_scope():
    moment = Moment()
    moment.append("MX", [7])
    cloned = moment.with_mapped_qubit_indices({7: 2})
    (old,) = moment.instructions
    (new,) = cloned.instructions
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
    first.append("RX", [0])
    second.append("RZ", [1])
    merged = first + second
    assert merged.qubits_indices == {0, 1}
    assert merged.filter_by_qubits([0]).qubits_indices == {0}
    with pytest.raises(MultipleOperationsOnSameQubitError):
        merged.append("H", [0])
    with pytest.raises(MultipleOperationsOnSameQubitError):
        first + first


def test_native_memory_spatial_path_without_stim(monkeypatch):
    import stim

    from tests.experiment.cases import make_graph
    from tqec.compile.compile import compile_block_graph
    from tqec.compile.tree.annotators.observables import get_ordered_leaves

    def forbidden(*args, **kwargs):
        raise AssertionError("Stim construction reached from native physical generation")

    monkeypatch.setattr(stim, "Circuit", forbidden)
    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    tree.get_native_module(1).verify()
    tree._annotate_circuits(1)
    for leaf in get_ordered_leaves(tree._root):
        leaf.get_annotations(1).circuit.get_native_module().verify()


def test_native_serialization():
    moment = Moment()
    moment.append("RX", [4, 0])
    assert Moment.from_dict(moment.to_dict()) == moment


def test_shared_measurement_dedup_and_repeated_identity():
    from tqec.circuit.measurement_map import MeasurementRecordsMap
    from tqec.circuit.schedule.manipulation import merge_scheduled_circuits

    qmap = QubitMap({0: GridQubit(1, 2)})
    measurement = Moment()
    measurement.append("M", [0])
    fragment = ScheduledCircuit([measurement], [0], qmap)
    merged = merge_scheduled_circuits([fragment, deepcopy(fragment)], qmap, {"M"})
    assert merged.num_measurements == 1
    repeated = ScheduledCircuit(
        [deepcopy(next(merged.moments)), deepcopy(next(merged.moments))], [0, 3], qmap
    )
    assert MeasurementRecordsMap.from_scheduled_circuit(repeated).mapping == {
        GridQubit(1, 2): [-2, -1]
    }
    module = repeated.get_native_module()
    module.verify()
    results = [op.results[0] for op in module.walk() if isinstance(op, qref.MeasureOp)]
    assert len(results) == 2 and results[0] is not results[1]
    with pytest.raises(MultipleOperationsOnSameQubitError):
        merge_scheduled_circuits([fragment, fragment], qmap)


def test_explicit_unsupported_paths_and_budget():
    import stim

    from tests.experiment.cases import make_graph
    from tqec.compile.compile import compile_block_graph
    from tqec.utils.exceptions import TQECError

    with pytest.raises(TQECError, match="Stim"):
        ScheduledCircuit.from_circuit(stim.Circuit("H 0"))
    with pytest.raises(TQECError, match="Unsupported"):
        Moment().append("S", [0])
    tree = compile_block_graph(make_graph("memory_z")).to_layer_tree()
    with pytest.raises(TQECError, match="budget"):
        tree.get_native_module(2, max_rounds=1)
    with pytest.raises(TQECError, match="observables"):
        tree.get_native_module(1, annotation_mode="auto", include_observables=True)
