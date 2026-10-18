"""Clifford boundary relations for reset, unitary, measurement fragments.

Paulis use the exact convention i**phase X**x Z**z. Integer bit masks and
measurement parity masks are private algebraic working data, not a circuit IR.
"""

from tqec.compile.lowering.base import UnsupportedLoweringError


def _multiply(a, b):
    x, z, phase = a
    u, v, other = b
    return x ^ u, z ^ v, (phase + other + 2 * (z & u).bit_count()) % 4


def _single(basis: str, bit: int):
    return (bit if basis in "XY" else 0, bit if basis in "YZ" else 0, int(basis == "Y"))


def _conjugate(pauli, gate: str, targets: tuple[int, ...]):
    x, z, phase = pauli
    a = 1 << targets[0]
    if gate == "H":
        phase += 2 * bool(x & z & a)
        if bool(x & a) != bool(z & a):
            x ^= a
            z ^= a
    elif gate in {"S", "S_DAG"}:
        if x & a:
            phase += 1 if gate == "S" else -1
            z ^= a
    elif gate in {"X", "Y", "Z"}:
        u, v, _ = _single(gate, a)
        phase += 2 * (((x & v).bit_count() + (z & u).bit_count()) % 2)
    elif gate == "CX":
        b = 1 << targets[1]
        if x & a:
            x ^= b
        if z & b:
            z ^= a
    elif gate in {"CZ", "CY"}:
        q = (targets[1],)
        before, after = ("H", "H") if gate == "CZ" else ("S_DAG", "S")
        return _conjugate(_conjugate(_conjugate(pauli, before, q), "CX", targets), after, q)
    else:
        raise UnsupportedLoweringError("bloq", gate, "no Clifford propagation rule")
    return x, z, phase % 4


def _dependencies(vectors):
    """Return independent combinations whose XOR is zero."""
    pivots = {}
    for index, original in enumerate(vectors):
        vector = original
        combination = 1 << index
        while vector:
            pivot = vector.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = (vector, combination)
                break
            row, mask = pivots[pivot]
            vector ^= row
            combination ^= mask
        if not vector:
            yield combination


def _combine(rows, mask):
    pauli = (0, 0, 0)
    measurements = 0
    for index, (p, records) in enumerate(rows):
        if mask >> index & 1:
            pauli = _multiply(pauli, p)
            measurements ^= records
    return pauli, measurements


def _collapse(rows, collapsing, measurement_ids):
    # A relation survives measurement/reset iff it commutes with each local
    # collapsing operator. Nullspace combinations retain joint checks even when
    # individual generators anticommute (e.g. a changed stabilizer boundary).
    anticommutations = []
    for (x, z, _), _records in rows:
        signature = 0
        for index, (q, basis) in enumerate(collapsing):
            u, v, _ = _single(basis, 1 << q)
            if ((x & v).bit_count() + (z & u).bit_count()) % 2:
                signature |= 1 << index
        anticommutations.append(signature)
    result = []
    for combination in _dependencies(anticommutations):
        (x, z, phase), records = _combine(rows, combination)
        for index, (q, basis) in enumerate(collapsing):
            bit = 1 << q
            if (x | z) & bit:
                if basis == "Y":
                    phase -= 1
                x &= ~bit
                z &= ~bit
                if measurement_ids is not None:
                    records ^= 1 << measurement_ids[index]
        sign = (phase - (x & z).bit_count()) % 4
        if sign not in (0, 2):
            raise UnsupportedLoweringError("bloq", "flow", "non-Hermitian boundary relation")
        result.append((x, z, records, sign // 2))
    return result


def fragment_flows(moments, qubits):
    """Compute creation and destruction flows from commuting reset/measurement fronts.

    Reject interleaved noncommuting fronts instead of treating them as a
    Clifford-only fragment. Spatially disjoint resets and gates may share a tick.
    """
    index = {q: i for i, q in enumerate(qubits)}
    resets = []
    measurements = []
    unitaries = []
    touched = set()
    measured = set()
    for moment in moments:
        for gate, targets in moment:
            ids = tuple(index[q] for q in targets)
            if gate.startswith("R"):
                if any(q in touched for q in ids):
                    raise UnsupportedLoweringError(
                        "bloq", "flow", "reset after an operation on the same qubit"
                    )
                resets.extend((q, gate[-1] if gate != "R" else "Z") for q in ids)
            elif gate.startswith("M"):
                if any(q in measured for q in ids):
                    raise UnsupportedLoweringError(
                        "bloq", "flow", "multiple measurements on one fragment qubit"
                    )
                measurements.extend((q, gate[-1] if gate != "M" else "Z") for q in ids)
                measured.update(ids)
            else:
                if any(q in measured for q in ids):
                    raise UnsupportedLoweringError(
                        "bloq", "flow", "gate after measurement on the same qubit"
                    )
                unitaries.append((gate, ids))
            touched.update(ids)
    creation = []
    for q, basis in resets:
        pauli = _single(basis, 1 << q)
        for gate, targets in unitaries:
            pauli = _conjugate(pauli, gate, targets)
        creation.append((pauli, 0))
    destruction = []
    for record, (q, basis) in enumerate(measurements):
        pauli = _single(basis, 1 << q)
        for gate, targets in reversed(unitaries):
            inverse = {"S": "S_DAG", "S_DAG": "S"}.get(gate, gate)
            pauli = _conjugate(pauli, inverse, targets)
        destruction.append((pauli, 1 << record))
    return (
        _collapse(creation, measurements, list(range(len(measurements)))),
        _collapse(destruction, resets, None),
    )


def closed_relations(flows, num_qubits):
    """Find all independent relations with no remaining Pauli boundary."""
    for mask in _dependencies([x | (z << num_qubits) for x, z, _, _ in flows]):
        # All boundary operators in a family commute. Include multiplication
        # signs instead of assuming every CSS-derived check is positive.
        pauli = (0, 0, 0)
        records = 0
        for index, (x, z, parity, sign) in enumerate(flows):
            if mask >> index & 1:
                pauli = _multiply(pauli, (x, z, (x & z).bit_count() + 2 * sign))
                records ^= parity
        if records:
            yield records, pauli[2] // 2
