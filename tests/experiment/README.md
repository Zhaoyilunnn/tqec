# Direct Deltakit ScheduledCircuit experiment

Upstream baseline: `2cfbbba4cc4696f011f630d279da36aacda529ca`.
Comparison branch: `refactor/stim-spec-lowering-20261018` at `1a1b14dd2`.
Dependencies: `requirements/deltakit-test.txt`; Python 3.11.16, Stim 1.16.0.

`capture.py` runs on the unmodified upstream checkout and records compact
physical, footprint and exact-output fingerprints for 42 cases. Temporary Stim
outputs under `/tmp/direct-baseline-*.stim` support independent differential
checks during the experiment. These files are reference evidence, never inputs
to native physical construction. `smoke_test.py` tests import interoperability
only; it does not establish native generation.
