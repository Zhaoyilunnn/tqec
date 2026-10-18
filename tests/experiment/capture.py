"""Capture compact, independently reproducible upstream circuit fingerprints."""
import hashlib
import json
from pathlib import Path

from tests.experiment.cases import CASES, CONVENTIONS, make_graph
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase


def physical(circuit):
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
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    rows = {}
    for name, convention in CONVENTIONS.items():
        for case in CASES:
            for k in (1, 2):
                circuit = compile_block_graph(make_graph(case), convention).generate_stim_circuit(
                    k, detector_database=DetectorDatabase(), database_path=None)
                key = f"{name}-{case}-{k}"
                Path(f"/tmp/direct-baseline-{key}.stim").write_text(str(circuit))
                rows[key] = {"physical": digest(physical(circuit)),
                             "measurements": circuit.num_measurements,
                             "qubits": digest(circuit.get_final_qubit_coordinates()),
                             "stim": hashlib.sha256(str(circuit).encode()).hexdigest()}
                print(key, flush=True)
    Path("tests/experiment/baseline.json").write_text(json.dumps(rows, indent=2)+"\n")
