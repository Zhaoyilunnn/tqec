Bloq text output
================

``tqec.compile.lowering.bloq`` emits native ``BLOQIR 1`` text directly from a
spec-backed ``LayerTree``. It preserves TQEC's physical construction and does
not call the Bloq block compiler. Text emission imports neither Stim, tqecd nor
Bloq. Temporary operation lists and integer Pauli masks exist only during
emission; there is no additional public circuit representation.

Generate a memory experiment
----------------------------

.. code-block:: python

   from pathlib import Path

   from tqec.compile.compile import compile_block_graph
   from tqec.compile.lowering.bloq import emit_bloq_text
   from tqec.computation.block_graph import BlockGraph
   from tqec.utils.position import Position3D

   graph = BlockGraph("Z memory")
   graph.add_cube(Position3D(0, 0, 0), "XZZ")
   tree = compile_block_graph(graph).to_layer_tree()
   text = emit_bloq_text(tree, k=1)
   Path("memory.bloqir").write_text(text, encoding="utf-8")

The default output includes physical operations, proven stabilizer boundary
flows, detectors and indexed logical observables. ``gates_only=True`` requests
only physical operations and ordering. Its metadata explicitly says
``gates-only``; it is not a complete QEC result.

For a spatial pipe, extend the same graph before compiling:

.. code-block:: python

   graph.add_cube(Position3D(0, 1, 0), "XZZ")
   graph.add_pipe(Position3D(0, 0, 0), Position3D(0, 1, 0))
   tree = compile_block_graph(graph).to_layer_tree()
   Path("spatial.bloqir").write_text(emit_bloq_text(tree, k=2), encoding="utf-8")

Load and validate with Bloq
---------------------------

The optional loader is pinned to **bloq-py 0.1.1**, whose import name is ``bloq``.
Install it separately in the environment used for TQEC:

.. code-block:: console

   python -m pip install bloq-py==0.1.1

.. code-block:: python

   from tqec.compile.lowering.bloq import lower_to_bloq

   program = lower_to_bloq(tree, k=2)
   program.validate()
   program.save("spatial.bloq")
   text_again = program.to_text()

``lower_to_bloq`` checks the installed version, parses the text and validates the
program by default. ``validate=False`` skips the last step. Text generation does
not require the optional package. Parser acceptance and validation are structural
checks; the backend's independent differential tests establish physical and QEC
equivalence for the supported constructions.

Supported constructions
-----------------------

The end-to-end matrix covers X memory, Z memory, temporal pipes, spatial pipes,
CNOT, three-arm junctions and temporal Hadamard. Each is tested at ``k=1,2`` with
fixed bulk, diagonal fixed bulk and fixed boundary conventions. Local tests also
cover every extended-plaquette shape, both halves, both orientations, reversal,
data initialization and measurement, and realignment boundary projections.
Negative block coordinates and an observable with an unrelated temporal-H
component have dedicated differential tests.

This is a backend for closed, prepared and measured static Clifford experiments.
The existing compiler rejects unfilled logical ports before lowering. The emitter
does not invent logical input or output operators for those ports, decoder
feedback, conditional execution or dynamic control. Diagonal spatial-H remains
outside this validated matrix. Custom translators, custom plaquette compiler
passes and concrete circuit layers cannot be recovered from construction specs;
``UnsupportedLoweringError`` identifies the offending construction and location.

Physical and measurement ownership
----------------------------------

Each complete spatial slice is merged before it becomes a Bloq template. Spatial
pipe substitutions, template indices, coordinate shifts and border trimming come
from the existing layout. Equal shared resets, measurements and Hadamards merge;
conflicting operations on one qubit raise an error. Empty moments are retained.
``reschedule_measurements=True`` aligns measurements to the layout's existing
measurement schedule. Setting it to ``False`` retains each spec's local schedule.
Complete QEC emission requires at most one measurement per qubit in each fragment.
For example, an unaligned fixed-boundary junction has repeated readouts within
one fragment: physical ``gates_only`` emission is available, but complete emission
raises an error. Use the default measurement alignment for that construction.

``tN`` identifies a reusable template. ``iN`` identifies a unique placement, even
when several placements reuse the same template. ``mN`` is local to a template;
``iN:mM`` identifies one actual measurement output. Spatial deduplication happens
before measurement IDs are assigned. Cross-instance parities cannot accidentally
refer to a template-local record.

``nN`` identifies a graph node. Each quantum node contains one complete time
slice and its construction block provenance. Source z coordinates are the
normalized construction-tree slice indices. Temporal pipes have already been
absorbed into cube constructions by this stage. Ordered graph edges preserve
physical chronology, including extra separators around nested and empty repeats.
The emitter does not infer source temporal pipes or manufacture quantum edges
from mere adjacency. Flows and explicit cross-instance parities carry the tested
stabilizer relations across these boundaries.

QEC relations
-------------

The backend propagates Pauli operators with exact Clifford conjugation and phase
tracking. A fragment's resets produce outgoing relations; measurements produce
incoming relations. Commuting combinations survive reset and measurement fronts.
Each emitted boundary flow is verified against Stim's flow checker in tests.
Production emission does not use that checker.

Detectors come from closed relations within a fragment or across adjacent
fragments. Their relation space is intersected with a radius-two plaquette
neighborhood and must contain a measurement owned by that construction's
syndrome qubit. This excludes global deterministic logical readouts from local
syndrome checks. A separate linear independence check rejects an observable that
falls inside the detector space. Detector bases can differ from the Stim backend;
tests compare their entire parity spaces, determinism and small-code distances.
Bloq detector coordinates are spatial pairs; graph order and instance ownership
preserve their temporal context.

Logical observables use the existing correlation surfaces and observable
builder. Bottom stabilizer contributions belong to the first layer of their
source time slice. Top readouts and temporal-H realignment contributions use the
instances that actually measure the contributing qubits. A disconnected
component does not change that ownership.

The construction tree remains available after emission. Stim output before or
after Bloq output uses its own cached tree and does not replace the specs.

Expansion limits and performance
--------------------------------

Repetitions are unrolled into distinct instances. Identical circuits with
identical side tables share templates. Compressed repeat bodies, recurrence
states and detector bundles are not emitted by this version.

The keyword budgets default to ``max_instances=10000``,
``max_plaquettes=100000`` and ``max_qubits=2048``. The plaquette limit counts dense
template cells across all instances, including empty cells, and is checked before
allocating each template array. A traversal limit also bounds separators from
nested empty repeats. The qubit limit bounds the Pauli propagation
problem. Exceeding a budget raises ``UnsupportedLoweringError``; increasing a
budget explicitly permits additional work. These limits bound input expansion,
not wall-clock execution time. Large Clifford propagation and unrolled cross-round
parities can still be expensive.

Run ``python benchmarks/bloq_text.py`` to measure a scale-two memory and a memory
with 100 repeated rounds. It reports reusable template count, instance count,
stored detector declarations, text size, elapsed emission time and peak traced
Python allocations. Stored declarations count each pooled template only once;
they are not the expanded circuit's detector count.

Validation
----------

.. code-block:: console

   python -m pytest tests/compile/lowering/bloq

With the pinned optional package installed, this runs real text and binary
round trips and Bloq-to-Stim differential checks. Without it, those integration
checks are skipped; pure emission, import isolation, local gate and flow tests
still run. The independent pre-refactor Stim snapshots and existing compile
integration tests are unchanged.
