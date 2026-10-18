Native Deltakit backend
=======================

The optional Deltakit backend builds a native ``CircuitProgram`` directly from
specification-backed layers. ``LogicalAssembler`` produces an xDSL ``ModuleOp``.
The producer does not import Stim, the Stim materializer, or the Bloq backend.
Deltakit's own dependency on ``deltakit-stim`` remains required.

Installation and entry points
-----------------------------

Install TQEC first, then install the pinned optional dependencies from the
repository root::

    uv pip install -r requirements/deltakit-test.txt

The tested source is Deltakit-compile commit
``e242562f1387b7efdff23d2bc7ea351f8b6edd03`` (version 0.1.0), with xDSL 0.68.0
and deltakit-stim 0.2.7. The adapter checks these three versions at runtime.
Use the pinned source requirement: the package version alone does not identify
an upstream commit. Python 3.11 is locally tested; CI also targets Python 3.12.

.. code-block:: python

    from tqec.compile.lowering.deltakit import (
        DeltakitOptions,
        build_deltakit_program,
        compile_to_deltakit,
        lower_to_deltakit_ir,
    )

    tree = compiled.to_layer_tree()
    module = lower_to_deltakit_ir(tree, k=1)
    module.verify()
    result = compile_to_deltakit(tree, k=1, export="stim")
    text = result.program
    capability = result.auxiliary_outputs["tqec.capability"]

``compiled`` is the result of ``compile_block_graph``. The tree retains its
construction root when another backend or scale is used. The default export
is ``physical-ir``. ``result.module`` is native IR; ``result.program`` is the
exported text. ``build_deltakit_program`` returns the native program before
assembler passes, for downstream users who need their own pass configuration.
``CircuitProgram`` is immutable and its ``module`` property returns a copy.
The assembler transforms that copy; passing a bare module permits in-place changes.

Annotation modes
----------------

``explicit`` is the default. Local Clifford algebra proves signed boundary
flows and local detector parities without calling a Stim detector finder.
Measurement results use native SSA values: each value identifies the result of
one measurement operation. Reused native fragments return these values to the
calling scope. Correlation surfaces resolve logical parities against their
owning layer and qubit, including temporal realignment.

The tested static QEC matrix covers X memory, Z memory, a temporal pipe, a spatial
pipe, CNOT, a three-arm junction, and temporal Hadamard, at scales 1 and 2 in
fixed bulk, diagonal fixed bulk, and fixed boundary conventions. Tests compare
physical moments, detector rank and span, logical parities, and noiseless
determinism. Memory and spatial-pipe tests additionally check distance under
the same depolarizing noise model. This coverage does not establish arbitrary
circuit support or matching-decoder performance for every detector basis.

``none`` produces physical operations without flows or detectors. If the tree
has logical observables, choose whether to preserve their uncorrected readout
recipes explicitly:

.. code-block:: python

    options = DeltakitOptions(annotation_mode="none", include_observables=False)
    module = lower_to_deltakit_ir(tree, 1, options=options)

``auto`` invokes the native stabilizer-flow pipeline. It is experimental and
requires ``include_observables=False``. In the tested X and Z memories at scales
1 and 2, its checks are deterministic but contain one additional independent
constraint compared with the reference detector space. This constraint includes
the logical readout; the output is not an interchangeable QEC detector basis.
Capability metadata and exported Stim comments identify this mode as
``experimental-auto``. It must not be used as a detector-complete replacement.

Physical timing and native operations
-------------------------------------

Each TQEC moment becomes a native lockstep parallel operation. Sparse empty
moments use the native ``TickAnnotationOp``. Spatial seam replacement happens
before gate emission. The adapter preserves unused declared qubit coordinates
as well as operated qubits. The default measurement rescheduling follows the
existing TQEC convention.

Logical observables receive fixed native IDs. Their uncorrected values feed a
native ``qstruct.OutputOp`` so optimization preserves each observable. No
correction request, decoder wait, or feedback is inserted. The output operation
also avoids a recursive copy in the pinned builder's classical-return path.
These two small native-operation insertions are confined to this backend.

Local flow tests invoke native ``VerifyFlows`` for representative relations from both
boundary directions with explicit input-state arguments. An independent signed
oracle checks every declared relation. Native
verification checks flows up to sign. Arbitrary incoming fragment contracts
cannot be attached directly to a freshly allocated state. Redundant creation
contracts also cannot share a single native ``FlowAttr`` output index. Do not
assume that enabling the complete native flow pipeline on an explicitly
annotated program is supported; the adapter's explicit mode uses its verified
parities directly.

Limits and diagnostics
----------------------

Only bounded unrolling is supported. Defaults allow 1,000 expanded slices,
100,000 plaquette cells and 2,048 physical qubits. Set
``max_unrolled_rounds``, ``max_plaquettes`` and ``max_qubits`` to lower application
limits. A limit is a refusal threshold, not a performance guarantee. Native
fragment definitions are reused before assembly; assembly may inline them.

Unknown specifications, concrete circuit layers, dynamic control, native quantum
loops, and relaxed scheduling are unsupported. Full annotations reject repeated
measurement of a qubit within one slice; this includes the unrescheduled fixed-boundary junction
case. Physical-only emission remains available for that construction. Signed
closed detector parities requiring an explicit correction are rejected rather
than silently inverted. Spatial-H cases with existing upstream failures are
not claimed as supported.

``UnsupportedLoweringError`` identifies the backend, construction and reason,
and includes a construction path where available. Native module attributes
``tqec.provenance`` record scale, expanded paths, reusable fragment count,
measurement count and slice count. Native compiler exceptions retain their
original diagnostics.

See ``tests/compile/lowering/deltakit/support_matrix.md`` for the exact validation
scope and ``tests/compile/lowering/deltakit/README.md`` for reproduction commands.
