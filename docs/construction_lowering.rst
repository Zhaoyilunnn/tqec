Physical construction and Stim lowering
=======================================

``compile_block_graph`` builds scalable physical constructions for TQEC's built-in
fixed-bulk and fixed-boundary conventions. The result stores templates and
immutable plaquette specifications. It does not create Stim circuits, moments or
scheduled circuits. ``to_layer_tree`` preserves this representation, including
nested sequences and scalable repetitions.

Construction specifications
---------------------------

``tqec.plaquette.spec`` defines three local construction descriptions:

* ``RPNGPlaquetteSpec`` stores the RPNG description and measurement schedule.
  Stim materialization always applies ``IdentityPlaquetteCompiler`` after RPNG
  translation, preserving ``ID(...)`` names and mergeable instructions.
* ``ExtendedPlaquetteSpec`` selects a shaped half of an extended stabilizer,
  including its orientation, reversed schedule, internal resets and measurements,
  and independent data-qubit operations for both halves.
* ``RealignmentPlaquetteSpec`` stores the fixed-bulk temporal Hadamard realignment
  parameters and any boundary projection.

These are parameters of existing TQEC constructions, not a general gate IR.
Their ``used_qubits`` and ``num_moments`` properties describe the existing physical
implementation. ``PlaquetteSpecs`` maps nonzero template indices to descriptions;
index zero continues to mean no plaquette. Updates and trimming return new
collections. ``SpecPlaquetteLayer`` and ``PlaquetteLayer`` share template geometry
and border trimming through ``TemplateLayer``.

``LayoutLayer.to_template_and_specs`` uses the same spatial pipe border mappings
as ``to_template_and_plaquettes``. ``LayoutLayer.qubits(k)`` can inspect either
representation. ``measurement_schedule`` gives the common measurement target;
rescheduling actual operations requires materialization first.

Physical output boundary
------------------------

``tqec.compile.lowering.stim.materializer.StimMaterializer`` translates specifications into
existing ``Plaquette`` and ``PlaquetteLayer`` objects. It calls the original RPNG,
extended stabilizer and realignment implementations. It preserves template
indices, trimmed borders, layer order and repetitions. Its local cache shares
materialized plaquettes; the existing measurement rescheduling operation creates
new objects instead of mutating cached circuits.

``LayerTree.construction_root`` exposes the original construction for other
backends. Circuit generation, streaming, visualization and serialization use a
separate, cached Stim tree. They leave the construction root and its specifications
unchanged. Rebuilding sequences and repetitions preserves their trimmed borders.
Circuit, detector, observable and polygon annotations therefore
continue to consume concrete layers. The existing generation APIs retain their
noise model, detector database, measurement scheduling and observable arguments.
Detector finding remains owned by the Stim and tqecd implementation. Existing
plaquette names and detector database keys are preserved, so this representation
change does not require a database version change.

Custom translators, custom plaquette compilation passes and ``RawCircuitLayer``
remain supported through the legacy Stim path. They can create circuits during
compilation. Their transformed timing and footprint cannot be inferred from the
built-in specifications, and they do not satisfy the compiler-only guarantee.
Direct calls to the builders and plaquette generators retain their concrete output;
``build_specs`` selects the built-in description path. When both compiler and
translator are omitted, their ``None`` defaults select the built-in policy without
importing backend implementations.
Explicit custom objects select the Stim-only path and execute their translation
and compilation passes during construction.

Stim implementation modules
---------------------------

The concrete implementation lives under ``tqec.compile.lowering.stim``:

* ``translator`` defines ``RPNGTranslator`` and ``DefaultRPNGTranslator``.
* ``compiler`` defines ``PlaquetteCompiler`` and ``IdentityPlaquetteCompiler``.
* ``css`` defines ``CSSPlaquetteCompiler``; ``passes`` contains its transformations.
* ``mapper`` provides ``PlaquetteMapper`` for direct concrete generation.
* ``extended_stabilizers`` and ``realignment`` implement the specialized plaquettes.
* ``materializer`` recursively lowers specifications and preserves layer metadata.

Import these objects from their implementation modules. The former translator and
compilation packages have been removed. Concrete mapper, extended stabilizer and
realignment helpers must also be imported from their new backend modules. Bare
translator calls still return names without ``ID(...)``; materializing an RPNG specification
always applies the identity policy, including for manually constructed specs.

Import boundary and installation
--------------------------------

In a fresh interpreter, importing ``tqec``, building supported ``BlockGraph``
objects, calling ``compile_block_graph`` with a built-in convention, and calling
``to_layer_tree`` do not import Stim, tqecd or the Stim backend package.
Physical output imports the backend and reports missing Stim dependencies at
that boundary. Explicit analysis functions that use Stim, such as stabilizer
reduction and CZ flow validation, still require Stim.

The installation dependencies remain unchanged. This change establishes code-level
import independence; it does not introduce a separately packaged compiler-only
extra or remove dependencies needed by the CLI and simulation tools.

Adding another physical backend
-------------------------------

``PlaquetteLowerer[PhysicalT_co]`` in ``tqec.compile.lowering.base`` defines local
lowering without prescribing the backend's physical output type. An adapter can
consume the specification collections, template offsets, sequences and repetitions
without modifying cube or pipe builders. It must implement every operation in a
supported specification and raise ``UnsupportedLoweringError`` for unsupported
constructions. The error exposes the backend, construction, reason and location.

An end-to-end adapter must additionally supply correct detector and logical
observable relations. Implementing the local protocol alone does not provide
those relations. No Bloq or Deltakit backend is implemented here.

.. list-table:: Current capability boundary
   :header-rows: 1
   :widths: 34 66

   * - Capability
     - Stim implementation
   * - Supported built-in Clifford constructions
     - RPNG, extended stabilizers and realignment retain existing behavior
   * - Reset, measurement and scheduled gate timing
     - Preserved from construction parameters
   * - Scalable repetition
     - Preserved structurally until output
   * - Custom translators, passes and raw circuits
     - Legacy Stim-only path
   * - Previously unsupported spatial Hadamard combinations
     - Existing exceptions remain in place
   * - Dynamic branches, repeat-until-success and decoder feedback
     - No new construction semantics or backend support

Validation
----------

``tests/compile/decoupling_baseline_test.py`` compares 42 exact circuit fingerprints
at scales one and two against upstream commit
``2cfbbba4cc4696f011f630d279da36aacda529ca``. The cases cover memory, spatial and
temporal pipes, CNOT, three-arm junctions and temporal Hadamard under fixed bulk,
diagonal fixed bulk and fixed boundary. Small memory cases also retain Stim text
snapshots. The tests check circuit counts and noiseless detector and observable
determinism using in-memory databases.

``tests/compile/lowering`` checks local round trips, metadata, import independence,
absence of physical constructors during compilation, streaming, repeated use at
different scales, and custom physical policies. Existing integration tests remain
unchanged and continue to check distance and explicit correlation surfaces.

A local five-sample CNOT benchmark with Python 3.11.16, Stim 1.16.0 and tqecd 0.2.1
measured the following medians. Detector databases were in memory. These timings
are local observations, not portable performance guarantees.

.. list-table:: Local median elapsed time in milliseconds
   :header-rows: 1

   * - Operation
     - Upstream baseline
     - Specification implementation
   * - Compile with a fresh convention
     - 57.4
     - 8.0
   * - Compile with a reused convention
     - 3.0
     - 2.4
   * - Generate the scale-one circuit
     - 1503.6
     - 1490.4
