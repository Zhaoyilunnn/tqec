"""Build native physical operations from specifications without circuit imports."""
# ruff: noqa: PLC0415

from importlib.metadata import version

from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.deltakit.config import DeltakitOptions
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
    if version("deltakit-compile") != "0.1.0" or version("xdsl") != "0.68.0":
        raise TQECError("Deltakit lowering requires deltakit-compile 0.1.0 and xdsl 0.68.0.")
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
    if options.annotation_mode != "none":
        raise UnsupportedLoweringError("deltakit", "annotations", "not yet validated")
    if tree._abstract_observables and options.include_observables is None:
        raise UnsupportedLoweringError(
            "deltakit",
            "observables",
            "physical-only output requires an explicit include_observables choice",
        )
    _require_dependency()
    from deltakit_compile.dialects.qstruct import OutputOp
    from deltakit_compile.dialects.stim import TickAnnotationOp
    from deltakit_compile.frontend.circuit import CircuitBuilder, ParallelAlignment, QubitReg
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
    placed = {q: register[i] for i, q in enumerate(coords)}
    records = []
    records_by_layer = []
    for moments in fragments:
        local = {}
        records_by_layer.append(local)
        for moment in moments:
            if not moment:
                builder._builder.append_ops_ignoring_ssas(TickAnnotationOp())
                continue
            with builder.parallel(ParallelAlignment.LOCKSTEP) as parallel:
                for gate, targets in moment:
                    with parallel():
                        if gate.startswith("M"):
                            local.setdefault(targets[0], []).append(len(records))
                            records.append(
                                builder.measure(
                                    "Z" if gate == "M" else gate[-1], placed[targets[0]]
                                )
                            )
                        else:
                            builder.gate(
                                "RZ" if gate == "R" else gate, [placed[q] for q in targets]
                            )
    if options.include_observables:
        for parity in observable_records(tree, k, layers, records_by_layer):
            observable = builder.declare_observable()
            observable.include([records[i] for i in parity])
            builder._builder.append_ops_ignoring_ssas(OutputOp([observable.get_uncorrected().ssa]))
    builder.add_return(records)
    fragment = builder.build("tqec_physical")
    program = CircuitProgramBuilder()
    register = program.declare_qubits(QubitReg(len(coords), qubit_locations=coords))
    program.add_return(program.call_circuit(fragment(register)))
    result = program.build_program()
    result.module.verify()
    return result


def compile_to_deltakit(
    tree: LayerTree, k: int, *, options=DeltakitOptions(), export="physical-ir"
):
    """Run the selected native pipeline and return Deltakit's CompilationResult."""
    program = build_deltakit_program(tree, k, options=options)
    from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
    from deltakit_compile.passes.logical_assembly.pipeline import PhysicalCircuitIRExportConfig
    from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

    if export not in {"physical-ir", "stim"}:
        raise ValueError("export must be physical-ir or stim.")
    config = (
        PhysicalCircuitIRExportConfig() if export == "physical-ir" else StimExportPipelineConfig()
    )
    result = LogicalAssembler(
        LogicalAssemblerConfig(export_config=config, stabiliser_flow_config=None)
    ).compile(program)
    result.module.verify()
    return result


def lower_to_deltakit_ir(tree: LayerTree, k: int, *, options=DeltakitOptions()):
    """Return the native xDSL physical ModuleOp without exporting a Stim circuit."""
    return compile_to_deltakit(tree, k, options=options).module
