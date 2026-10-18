"""One physical time slice stored as native Deltakit operations and qubit SSA."""
from __future__ import annotations

from copy import deepcopy

from deltakit_compile.dialects import qcore, qref
from xdsl.ir import Block

from tqec.circuit.native import gate_name, make_operation
from tqec.utils.exceptions import TQECError


class MultipleOperationsOnSameQubitError(TQECError):
    def __init__(self, qubits):
        self.qubits = sorted(qubits)
        super().__init__(f"Conflicting operations on qubits {self.qubits} in one moment.")


class Moment:
    """Own a native block; integer labels map directly to its qubit arguments."""

    def __init__(self, circuit=None, used_qubits=None, _avoid_checks=False):
        if circuit is not None and not isinstance(circuit, Block):
            raise TQECError("Moment requires a native xDSL Block; Stim storage is unsupported.")
        self._circuit = circuit if circuit is not None else Block()
        labels = list(range(len(self._circuit.args))) if used_qubits is None else sorted(used_qubits)
        if len(labels) != len(self._circuit.args):
            raise TQECError("Native qubit labels must match block arguments.")
        self._labels = labels
        self.check_is_valid_moment(self._circuit)

    @property
    def circuit(self):
        """Return the native block, never a Stim view."""
        return self._circuit

    @property
    def qubit_ssa(self):
        """Map the existing integer qubit labels to native block arguments."""
        return dict(zip(self._labels, self._circuit.args))

    def targets(self, op):
        """Resolve an operation's native qubit operands to local labels."""
        lookup = {arg: i for i, arg in self.qubit_ssa.items()}
        return [lookup[q] for q in op.operands]

    @staticmethod
    def check_is_valid_moment(block):
        """Reject unsupported operations and overlapping quantum resources."""
        seen = set()
        for op in block.ops:
            gate_name(op)
            for q in op.operands:
                if q not in block.args:
                    raise TQECError("Moment operation captures a qubit outside its native block.")
                if q in seen:
                    raise MultipleOperationsOnSameQubitError([q.index])
                seen.add(q)

    @property
    def instructions(self):
        """Iterate native operations without converting them."""
        return iter(self._circuit.ops)

    @property
    def qubits_indices(self):
        """Return the labels of operated qubits."""
        return {i for op in self.instructions for i in self.targets(op)}

    @property
    def num_measurements(self):
        """Count native measurement results."""
        return sum(len(op.results) for op in self.instructions if isinstance(op, qref.MeasureOp))

    @property
    def is_empty(self):
        """Return whether this block contains no physical operation."""
        return not bool(self._circuit.ops)

    def append(self, name, targets, args=()):
        """Build a native operation; strings are construction inputs, not stored IR."""
        if args:
            raise TQECError("Parameterized custom operations are unsupported in this experiment.")
        targets = list(targets)
        if not targets:
            return
        conflicts = self.qubits_indices.intersection(targets)
        if conflicts or len(targets) != len(set(targets)):
            raise MultipleOperationsOnSameQubitError(conflicts or targets)
        for i in targets:
            if i not in self._labels:
                self._labels.append(i)
                self._circuit.insert_arg(qcore.QubitType(), len(self._circuit.args))
        self._circuit.add_op(make_operation(name, [self.qubit_ssa[i] for i in targets]))

    def contains_instruction(self, name):
        """Test a physical gate name."""
        return any(gate_name(op) == name for op in self.instructions)

    def remove_all_instructions_inplace(self, names):
        """Remove matching operations, refusing dangling SSA uses."""
        for op in list(self.instructions):
            if gate_name(op) in names:
                self._circuit.erase_op(op)

    def with_mapped_qubit_indices(self, mapping):
        """Clone the native region and remap labels with native SSA substitution."""
        labels = [mapping[i] for i in self._labels]
        if len(set(labels)) != len(labels):
            raise TQECError("Qubit remapping must be injective.")
        result = Moment()
        result._labels = labels
        result._circuit = Block(arg_types=[qcore.QubitType() for _ in labels])
        values = dict(zip(self._circuit.args, result._circuit.args))
        for op in self.instructions:
            result._circuit.add_op(op.clone(value_mapper=values))
        return result

    def filter_by_qubits(self, keep):
        """Project native broadcasts, preserving complete multi-qubit groups."""
        keep = set(keep)
        result = Moment()
        for op in self.instructions:
            lookup = {arg: i for i, arg in self.qubit_ssa.items()}
            for group in op.qubit_operand_groups:
                targets = [lookup[q] for q in group]
                if set(targets) <= keep:
                    result.append(gate_name(op), targets)
        return result

    def __deepcopy__(self, memo):
        return self.with_mapped_qubit_indices({i: i for i in self._labels})

    def __copy__(self):
        return deepcopy(self)

    def __iadd__(self, other):
        conflicts = self.qubits_indices & other.qubits_indices
        if conflicts:
            raise MultipleOperationsOnSameQubitError(conflicts)
        for i in other._labels:
            if i not in self._labels:
                self._labels.append(i)
                self._circuit.insert_arg(qcore.QubitType(), len(self._circuit.args))
        mapping = {arg: self.qubit_ssa[i] for i, arg in other.qubit_ssa.items()}
        for op in other.instructions:
            self._circuit.add_op(op.clone(value_mapper=mapping))
        return self

    def __add__(self, other):
        result = deepcopy(self)
        result += other
        return result

    def append_annotation(self, instruction):
        """Reject old annotation objects rather than mixing representations."""
        raise TQECError("Attach annotations to the assembled native circuit or explicit export boundary.")

    def __eq__(self, other):
        return isinstance(other, Moment) and self._labels == other._labels and self._circuit.is_structurally_equivalent(other._circuit)

    @staticmethod
    def from_instructions(instructions):
        """Reject detached instructions without a qubit SSA scope."""
        raise TQECError("Construct Moment from a native block with explicit qubit arguments.")


def iter_stim_circuit_without_repeat_by_moments(*args, **kwargs):
    """Reject the legacy parser on the direct native path."""
    raise TQECError("Stim parsing is not supported by the native Moment implementation.")
