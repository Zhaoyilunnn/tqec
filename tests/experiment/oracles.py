"""Independent physical and QEC comparison at the explicit Stim export boundary."""

import hashlib
import json


def physical(circuit):
    """Normalize gates by physical coordinates and retain every internal tick."""
    coords = circuit.get_final_qubit_coordinates()
    moments = [[]]
    for op in circuit.flattened():
        if op.name == "TICK":
            moments.append([])
        elif op.name not in {"QUBIT_COORDS", "SHIFT_COORDS", "DETECTOR", "OBSERVABLE_INCLUDE"}:
            for group in op.target_groups():
                moments[-1].append((op.name, tuple(tuple(coords[q.value]) for q in group)))
    while moments and not moments[-1]:
        moments.pop()
    return [sorted(moment) for moment in moments]


def digest(data):
    """Hash a portable canonical representation."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def checks(circuit):
    """Express annotation parities in physical measurement identities."""
    coords = circuit.get_final_qubit_coordinates()
    records, detectors, observables = [], [], {}
    tick = 0
    for op in circuit.flattened():
        if op.name == "TICK":
            tick += 1
        elif op.name in {"M", "MX", "MY"}:
            records.extend((tick, tuple(coords[t.value])) for t in op.targets_copy())
        elif op.name in {"DETECTOR", "OBSERVABLE_INCLUDE"}:
            parity = set()
            for target in op.targets_copy():
                parity.symmetric_difference_update([records[target.value]])
            if op.name == "DETECTOR":
                detectors.append(parity)
            else:
                observables.setdefault(
                    int(op.gate_args_copy()[0]), set()
                ).symmetric_difference_update(parity)
    return detectors, observables


def rank(rows):
    """Compute independent parity rank over GF(2)."""
    pivots = {}
    for original in rows:
        row = set(original)
        while row:
            pivot = max(row)
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row.symmetric_difference_update(pivots[pivot])
    return len(pivots)


def canonical_space(rows):
    """Canonical reduced GF(2) basis over physical measurement identities."""
    pivots = {}
    for original in rows:
        row = set(original)
        while row:
            pivot = max(row)
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row.symmetric_difference_update(pivots[pivot])
    for pivot in sorted(pivots):
        for other, row in pivots.items():
            if other != pivot and pivot in row:
                row.symmetric_difference_update(pivots[pivot])
    return sorted(sorted(row) for row in pivots.values())
