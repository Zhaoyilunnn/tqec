Direct Deltakit ScheduledCircuit experiment
===========================================

This branch is a bounded static-circuit experiment based on upstream commit
``2cfbbba4cc4696f011f630d279da36aacda529ca``. It retains concrete ``Plaquette``,
``ScheduledCircuit``, ``LayoutLayer`` and ``LayerTree`` objects. ``Moment`` owns
native Deltakit operations in an xDSL block. There is no PlaquetteSpec layer,
TQEC gate IR or Stim import in physical construction.

Installation and use
--------------------

Python 3.11 or later is required. The pinned Deltakit source revision is
``e242562f1387b7efdff23d2bc7ea351f8b6edd03``, with xDSL 0.68.0 and deltakit-stim
0.2.7. These are mandatory dependencies on this experimental branch::

    uv sync --locked --group test
    uv run pytest tests/experiment -q -o timeout=240

For a compiled graph, the native and simulation interfaces are::

    tree = compile_block_graph(graph).to_layer_tree()
    physical = tree.get_native_module(1)
    physical.verify()
    annotated = tree.get_native_module(
        1, annotation_mode="legacy", include_observables=True
    )
    circuit = tree.generate_circuit(1)

``generate_circuit`` exports the assembled native module to original Stim for
simulation. ``annotation_mode="none"`` constructs only physical operations;
``include_observables=True`` can add logical readouts independently.
``annotation_mode="legacy"`` first assembles and verifies native physical IR,
then exports fragments for the existing Stim-based tqecd detector algorithm.
Its detector relations are attached using native measurement SSA values.
Detector finding in this mode still depends on Stim.

``annotation_mode="auto"`` runs Deltakit's native stabiliser-flow pipeline.
Only X and Z memory have been validated in this mode. It rejects
``include_observables=True``. It must not be
substituted for legacy mode in logical-error-rate simulations: even a memory
circuit acquires an additional deterministic logical-readout constraint.

Representation and scope
------------------------

* Native qubit block arguments are associated with the existing integer labels
  and QubitMap coordinates. Cloning rebinds operands through xDSL value maps.
  A moment cannot capture a qubit from another block.
* Native broadcasts are split during spatial merging. Only explicitly mergeable
  reset and measurement operations are deduplicated; conflicting uses fail.
* Each scheduled moment becomes a native parallel region. Its measurement
  results are returned to the enclosing circuit before annotations consume them.
  Record offsets are compatibility queries derived from native measurements.
* Repetitions are expanded at the requested ``k`` with a default limit of 1000
  layer instances, 2048 allocated qubits and 100000 cells per layout. Native
  quantum loops and dynamic decoder feedback are outside this experiment.
* Observable attribution follows each observable's spatial slice and the actual
  final measurement of each participating qubit, including realignment. It does
  not use the last global leaf as a readout proxy.
* Memory, spatial and temporal pipes, CNOT, extended junctions and temporal
  Hadamard are covered at ``k=1,2`` under bulk, diagonal and boundary conventions
  in physical-only and legacy annotation modes.

Compatibility changes
---------------------

``Moment.circuit`` is now a native block; ``Moment.instructions`` yields native
operations. Arbitrary Stim input through ``Moment`` or
``ScheduledCircuit.from_circuit`` is rejected. Native Moment serialization uses
xDSL region text; old Stim-backed serialized caches require regeneration.

Supported construction gates are X, Y, Z, H, CX, CY, CZ, single-qubit Pauli
resets and single-qubit Pauli measurements. Noisy measurements, mixed-basis
broadcasts and multi-qubit Pauli measurements are rejected. Noise is applied
after the final Stim export using the existing NoiseModel.

The built-in conventions need only the identity plaquette compiler. Nonempty
custom PlaquetteCompiler pass lists and the old instruction-rewriting passes
fail explicitly. Arbitrary raw circuit layers are not supported by native tree
assembly. Existing downstream Stim visualization and simulation consumers remain;
legacy per-node assembly and annotation mutation are not native extension APIs.
Crumble URL generation requires ``add_polygons=False``.
The circuit stream interface currently yields a materialized full circuit;
incremental streaming and legacy disk detector caches are not supported.

The unchanged old low-level tests that construct Stim-backed Moments are not a
compatibility target. The existing ``tests/compile/compile_test.py`` is unchanged
and is used to check high-level behavior, including noise and graphlike distance.
This branch is not a drop-in replacement for the full upstream public API.

Evidence and assessment
-----------------------

``tests/experiment/baseline.json`` contains compact fingerprints captured from
the pinned upstream revision before implementation. Four small original memory
circuits are retained as import-interoperability controls. Physical comparison
preserves internal ticks, gate orientation, measurement basis and coordinates.
QEC comparison uses a canonical reduced GF(2) basis of detector parities over
physical measurement identities; observable parities are compared separately.
Trailing empty ticks are normalized because Deltakit terminates parallel regions
with a tick. Raw instruction strings and detector basis ordering need not match.

The executable benchmark is ``tests/experiment/performance.py``. Run it in
separate processes for upstream, spec and direct source checkouts, using this
branch's same Python environment. It warms each route once, records three wall
clock runs, and separately measures peak Python allocations with tracemalloc.
Every run constructs a new tree and a fresh detector database. Library caches
remain warm. The spec route uses explicit Deltakit QEC lowering; the direct route
uses legacy QEC and final native Stim export. All routes compile Z memory with
observables. Peaks exclude C++ allocations, and this small benchmark does not
establish large-scale performance or Monte Carlo error rates.

Detailed local measurements and checks are recorded in
``tests/experiment/assessment.json``. The comparison spec revision is
``1a1b14dd296e1cf4f3543ba83a5387f23c81e327``.

The direct route rewrites six core responsibilities: Moment ownership and SSA
transforms, scheduled native export, native plaquette generation, spatial merge,
bounded tree assembly, and measurement-to-annotation binding. It preserves the
logical graph and layout algorithms. Its smaller source diff partly reflects
removing old public behavior and supporting only one backend; it is not evidence
that the same complete feature set costs less. The spec comparison also provides
Stim and Bloq outputs and stronger compatibility, so raw line counts alone do
not measure architectural quality.

The physical migration is real, but detector compatibility still retains the
Stim-based algorithm. Native auto finding is not a replacement for TQEC logical
QEC semantics. The experiment therefore supports keeping the spec boundary for
the multi-backend fork and retaining this direct branch for investigation of
native transformations. It does not support merging this branch as a transparent
library substitution.

Local validation results
------------------------

The final run passed 42 physical-equivalence cases and 42 legacy-QEC cases.
All 139 selected tests in the unchanged upstream compile test file passed,
including graphlike-distance checks with uniform depolarizing noise of 0.001.
Seven native-core checks, four import controls and four auto-finding checks also
passed. The auto relations equal the span of the original memory detectors and
its logical observable; they do not equal the original detector space alone.
No Monte Carlo logical-error-rate estimate was performed.

Source type checking, pre-commit hooks, locked dependency resolution, wheel
building and source-distribution building passed. The documentation build
succeeded with warnings from stale generated ``import_module`` autosummary
stubs. The source diff against the pinned upstream is 15 files, 651 inserted
lines and 896 deleted lines. The spec comparison changes 80 source files,
with 3269 insertions and 571 deletions; its scope includes three backends.

The following timings are medians of three untraced warmed runs. Peak Python
allocations were measured separately, after all test jobs had finished.

.. list-table:: Z-memory compilation and final QEC export
   :header-rows: 1

   * - Route
     - k
     - Median seconds
     - Peak Python MiB
   * - upstream
     - 1
     - 0.200
     - 0.27
   * - upstream
     - 2
     - 0.320
     - 0.61
   * - spec
     - 1
     - 0.531
     - 5.07
   * - spec
     - 2
     - 1.959
     - 17.92
   * - direct
     - 1
     - 1.927
     - 4.37
   * - direct
     - 2
     - 9.789
     - 11.79

The direct route retains repeated fragment exports for the legacy detector
algorithm. The recorded profiles identify the native compiler and export costs;
inclusive function times overlap and must not be added. Native Moment cloning
also allocates Python SSA objects, unlike the upstream C++ Stim copy. These
measurements do not show a performance benefit from direct binding.

In the separate profiled direct ``k=2`` run, detector annotation occupied 28.18
of 31.28 instrumented seconds, including 120 scheduled-fragment exports and
122 native compiler calls. These instrumented durations include profiler overhead.
The measured slowdown describes this compatibility adapter; repeated compilation
at legacy query boundaries is a concrete optimization target.

A five-qubit measurement Moment deep copy averaged 1.48
microseconds upstream and 46.48 microseconds on the direct route
over 1000 copies. The spec route has no Moment object to copy.
