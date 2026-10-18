# Construction regression baseline

Captured at upstream `2cfbbba4cc4696f011f630d279da36aacda529ca`, with Python
3.11.16, Stim 1.16.0 and tqecd 0.2.1. Each JSON records a SHA-256 of the exact
ideal Stim text and circuit counts. Small memory circuits also have text snapshots.

The cases cover X and Z memory, temporal and spatial pipes, CNOT, a three-arm
spatial junction and temporal Hadamard, at k=1 and k=2, with fixed bulk, diagonal
fixed bulk and fixed boundary conventions. The junction exercises extended
stabilizers and fixed-boundary alternation. Existing integration tests cover
explicit correlation surfaces, distance and unsupported spatial Hadamard cases.

Regenerate only on the recorded upstream version:

```sh
TQEC_UPDATE_BASELINES=1 uv run pytest -q tests/compile/decoupling_baseline_test.py
```

The test uses an in-memory detector database and checks noiseless detector and
observable determinism. Initial run: 42 passed. Existing compiler, layout,
translator, detector computation and tree tests: 244 passed, 2 expected failures.
The existing tests were run with `TQEC_DETECTOR_DATABASE_PATH` pointing to a
file in a temporary directory to avoid changing the user's database.
