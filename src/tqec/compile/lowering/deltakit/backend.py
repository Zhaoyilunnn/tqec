"""Build native physical operations from specifications without circuit imports."""
# ruff: noqa: PLC0415

import json
from importlib.metadata import version

from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.deltakit.annotations import detector_recipes, indices
from tqec.compile.lowering.deltakit.config import DeltakitOptions
from tqec.compile.lowering.deltakit.flows import _dependencies
from tqec.compile.lowering.deltakit.fragments import build_fragment
from tqec.compile.lowering.deltakit.layout import layout_moments
from tqec.compile.lowering.deltakit.observables import observable_records
from tqec.compile.lowering.deltakit.tree import _timed_layers
from tqec.compile.tree.tree import LayerTree
from tqec.utils.exceptions import TQECError


def _require_dependency():
    try:
        import deltakit_compile
    except ModuleNotFoundError as error:
        raise TQECError(
            "Install the pinned deltakit-compile source to use this backend."
        ) from error
    if (version("deltakit-compile"), version("xdsl"), version("deltakit-stim")) != (
        "0.1.0",
        "0.68.0",
        "0.2.7",
    ):
        raise TQECError(
            "Deltakit lowering requires deltakit-compile 0.1.0, "
            "xdsl 0.68.0 and deltakit-stim 0.2.7."
        )
    return deltakit_compile


def build_deltakit_program(tree: LayerTree, k: int, *, options=DeltakitOptions()):
    """Build a native CircuitProgram, preserving physical time and measurement SSA."""
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer.")
    if any(
        type(v) is not int or v < 1
        for v in (options.max_unrolled_rounds, options.max_plaquettes, options.max_qubits)
    ):
        raise ValueError("Expansion budgets must be positive integers.")
    if options.repeat_mode != "unroll" or not options.strict_schedule:
        raise UnsupportedLoweringError("deltakit", "options", "requires strict bounded unrolling")
    if options.annotation_mode not in {"none", "explicit", "auto"}:
        raise ValueError("Unknown annotation mode.")
    if options.annotation_mode == "auto" and options.include_observables is not False:
        raise UnsupportedLoweringError(
            "deltakit",
            "automatic annotations",
            "experimental detector finding requires include_observables=False",
        )
    if (
        tree._abstract_observables
        and options.annotation_mode == "none"
        and options.include_observables is None
    ):
        raise UnsupportedLoweringError(
            "deltakit",
            "observables",
            "physical-only output requires an explicit include_observables choice",
        )
    _require_dependency()
    from deltakit_compile.dialects.qec import DecObservableOp
    from deltakit_compile.dialects.qstruct import OutputOp
    from deltakit_compile.dialects.stim import ObservableIdAttr
    from deltakit_compile.frontend.circuit import CircuitBuilder, QubitReg
    from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder

    fragments = []
    layers = []
    qubits = set()
    cells = 0
    for index, ((path, layer), padding) in enumerate(
        _timed_layers(tree.construction_root, k, options.max_unrolled_rounds)
    ):
        if index >= options.max_unrolled_rounds:
            raise UnsupportedLoweringError("deltakit", "repeat", "round budget exceeded", path)
        if not all(isinstance(child, SpecPlaquetteLayer) for child in layer.layers.values()):
            raise UnsupportedLoweringError("deltakit", "concrete layer", "requires specs", path)
        template, _ = layer.to_template_and_specs()
        shape = template.shape(k)
        cells += shape.x * shape.y
        if cells > options.max_plaquettes:
            raise UnsupportedLoweringError("deltakit", "layout", "cell budget exceeded", path)
        moments = [[] for _ in range(padding)] + layout_moments(
            layer, k, options.reschedule_measurements, path
        )
        qubits.update((q.x, q.y) for q in layer.qubits(k))
        if len(qubits) > options.max_qubits:
            raise UnsupportedLoweringError("deltakit", "layout", "qubit budget exceeded", path)
        fragments.append(moments)
        layers.append((path, layer))
    coords = sorted(qubits)
    builder = CircuitBuilder()
    register = builder.add_arg(QubitReg(len(coords)))
    records = []
    ownership = []
    offsets = []
    records_by_layer = []
    families = []
    pool = {}
    for index, moments in enumerate(fragments):
        signature = tuple(tuple(moment) for moment in moments)
        if signature not in pool:
            try:
                pool[signature] = build_fragment(
                    f"tqec_slice_{len(pool)}",
                    coords,
                    moments,
                    options.annotation_mode == "explicit",
                )
            except UnsupportedLoweringError as error:
                raise UnsupportedLoweringError(
                    "deltakit", error.construction, error.reason, layers[index][0]
                ) from error
        fragment, flows, local_qubits = pool[signature]
        offsets.append(len(records))
        families.append(flows)
        returned = builder.call_circuit(fragment(register))
        returned = (
            () if returned is None else returned if isinstance(returned, tuple) else (returned,)
        )
        if len(returned) != len(local_qubits):
            raise TQECError("Deltakit returned an inconsistent measurement signature.")
        local = {}
        for q in local_qubits:
            local.setdefault(q, []).append(len(ownership))
            ownership.append(q)
        records_by_layer.append(local)
        records.extend(returned)
    parities = list(observable_records(tree, k, layers, records_by_layer))
    detector_masks = []
    if options.annotation_mode == "explicit":
        for mask, center in detector_recipes(layers, k, families, ownership, offsets, coords):
            builder.detector([records[i] for i in indices(mask)], tuple(float(v) for v in center))
            detector_masks.append(mask)
        logical_masks = [sum(1 << i for i in parity) for parity in parities]
        if any(
            relation >> len(detector_masks)
            for relation in _dependencies(detector_masks + logical_masks)
        ):
            raise UnsupportedLoweringError(
                "deltakit", "logical readout", "observable is contained in the detector space"
            )
    if options.include_observables is not False:
        for observable_id, parity in enumerate(parities):
            observable = builder.declare_observable()
            declaration = observable.ssa.owner
            assert isinstance(declaration, DecObservableOp)
            ObservableIdAttr.set(declaration, observable_id)
            observable.include([records[i] for i in parity])
            builder._builder.append_ops_ignoring_ssas(OutputOp([observable.get_uncorrected().ssa]))
    builder.add_return(records)
    fragment = builder.build("tqec_physical")
    program = CircuitProgramBuilder()
    register = program.declare_qubits(QubitReg(len(coords), qubit_locations=coords))
    returned = program.call_circuit(fragment(register))
    if returned is not None:
        program.add_return(returned)
    result = program.build_program()
    from xdsl.dialects.builtin import StringAttr

    result.module.attributes["tqec.capability"] = StringAttr(
        {"none": "physical-only", "explicit": "static-qec", "auto": "experimental-auto"}[
            options.annotation_mode
        ]
    )
    result.module.attributes["tqec.provenance"] = StringAttr(
        json.dumps(
            {
                "scale": k,
                "paths": [path for path, _ in layers],
                "templates": len(pool),
                "measurements": len(records),
                "rounds": len(layers),
            }
        )
    )
    result.module.verify()
    return result


def compile_to_deltakit(
    tree: LayerTree, k: int, *, options=DeltakitOptions(), export="physical-ir"
):
    """Run the selected native pipeline and return Deltakit's CompilationResult."""
    program = build_deltakit_program(tree, k, options=options)
    from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
    from deltakit_compile.passes.logical_assembly.pipeline import PhysicalCircuitIRExportConfig
    from deltakit_compile.passes.stabiliser.pipeline import StabiliserFlowPipelineConfig
    from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

    if export not in {"physical-ir", "stim"}:
        raise ValueError("export must be physical-ir or stim.")
    config = (
        PhysicalCircuitIRExportConfig() if export == "physical-ir" else StimExportPipelineConfig()
    )
    result = LogicalAssembler(
        LogicalAssemblerConfig(
            export_config=config,
            stabiliser_flow_config=StabiliserFlowPipelineConfig()
            if options.annotation_mode == "auto"
            else None,
        )
    ).compile(program)
    result.module.verify()
    capability = {"none": "physical-only", "explicit": "static-qec", "auto": "experimental-auto"}[
        options.annotation_mode
    ]
    result.auxiliary_outputs = {**result.auxiliary_outputs, "tqec.capability": capability}
    if export == "stim":
        result.program = f"# TQEC Deltakit capability: {capability}\n" + result.program
    return result


def lower_to_deltakit_ir(tree: LayerTree, k: int, *, options=DeltakitOptions()):
    """Return the native xDSL physical ModuleOp without exporting a Stim circuit."""
    return compile_to_deltakit(tree, k, options=options).module
