# Direct Deltakit ScheduledCircuit experiment

Upstream baseline: `2cfbbba4cc4696f011f630d279da36aacda529ca`.
Comparison branch: `refactor/stim-spec-lowering-20261018` at `1a1b14dd2`.
Dependencies: `requirements/deltakit-test.txt`; Python 3.11.16, Stim 1.16.0.

Run `uv sync --locked --group test`, then `uv run pytest tests/experiment -q`.
The assessment and API limits are in
[the experiment report](../../docs/direct_deltakit_experiment.rst).

`capture.py` must run against the unmodified pinned upstream source. It records
physical, coordinate, detector-space and observable-parity fingerprints for 42
cases. Its temporary Stim outputs are reference evidence, never inputs to native
physical construction. Four memory outputs are retained in `fixtures` for
`smoke_test.py`, which tests import interoperability only. The physical and QEC
tests use compact `baseline.json` fingerprints and do not depend on `/tmp` files.
`native_core_test.py` prohibits Stim construction on the native generation path.

For comparisons, run `performance.py SOURCE_ROOT ROUTE K` in this environment,
where ROUTE is `upstream`, `spec` or `direct`. Use separate source checkouts at the
recorded commits. The script measures warmed compilation and separate allocation
and profiling runs. `assessment.json` retains local results and their limitations.
