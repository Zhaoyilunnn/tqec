"""Capture compact, independently reproducible upstream circuit fingerprints."""

import hashlib
import json
from pathlib import Path

from tests.experiment.cases import CASES, CONVENTIONS, make_graph
from tests.experiment.oracles import canonical_space, checks, digest, physical
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase

if __name__ == "__main__":
    rows = {}
    for name, convention in CONVENTIONS.items():
        for case in CASES:
            for k in (1, 2):
                circuit = compile_block_graph(make_graph(case), convention).generate_stim_circuit(
                    k, detector_database=DetectorDatabase(), database_path=None
                )
                key = f"{name}-{case}-{k}"
                Path(f"/tmp/direct-baseline-{key}.stim").write_text(str(circuit))
                rows[key] = {
                    "physical": digest(physical(circuit)),
                    "measurements": circuit.num_measurements,
                    "qubits": digest(circuit.get_final_qubit_coordinates()),
                    "stim": hashlib.sha256(str(circuit).encode()).hexdigest(),
                }
                ds, obs = checks(circuit)
                rows[key].update(
                    detector_space=digest(canonical_space(ds)),
                    detector_rank=len(canonical_space(ds)),
                    observables=digest({i: sorted(v) for i, v in obs.items()}),
                    coordinate_set=digest(sorted(circuit.get_final_qubit_coordinates().values())),
                )
                print(key, flush=True)
    Path("tests/experiment/baseline.json").write_text(json.dumps(rows, indent=2) + "\n")
