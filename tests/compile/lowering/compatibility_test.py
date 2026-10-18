from functools import partial

import pytest
import stim

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION, Convention, ConventionTriplet
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.stim.compiler import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.compile.lowering.stim.materializer import StimMaterializer
from tqec.compile.lowering.stim.passes.scheduling import ChangeSchedulePass
from tqec.compile.lowering.stim.translator import DefaultRPNGTranslator
from tqec.compile.specs.library.fixed_bulk import FixedBulkCubeBuilder, FixedBulkPipeBuilder
from tqec.computation.block_graph import BlockGraph
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.utils.instructions import MEASUREMENT_INSTRUCTION_NAMES, RESET_INSTRUCTION_NAMES
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D


def memory() -> BlockGraph:
    graph = BlockGraph()
    graph.add_cube(Position3D(0, 0, 0), "ZXZ")
    return graph


@pytest.mark.parametrize("reschedule", (False, True))
@pytest.mark.parametrize("noisy", (False, True))
def test_streaming_and_repeated_distances(reschedule: bool, noisy: bool) -> None:
    compiled = compile_block_graph(memory())
    noise = NoiseModel.uniform_depolarizing(0.001) if noisy else None
    generate = partial(
        compiled.generate_stim_circuit,
        noise_model=noise,
        detector_database=DetectorDatabase(),
        database_path=None,
        reschedule_measurements=reschedule,
    )
    first = generate(1)
    second = generate(2)
    streamed = sum(
        compiled.generate_stim_circuit_stream(
            1,
            noise_model=noise,
            detector_database=DetectorDatabase(),
            database_path=None,
            reschedule_measurements=reschedule,
        ),
        stim.Circuit(),
    )
    assert first.flattened() == streamed.flattened()
    assert first == generate(1)
    assert second.num_measurements > first.num_measurements
    assert first.num_detectors > 0
    assert first.num_observables == 1


@pytest.mark.parametrize("custom", ("translator", "compiler", "both"))
def test_custom_translator_and_passes_are_preserved(custom: str) -> None:
    class CountingTranslator(DefaultRPNGTranslator):
        def __init__(self):
            super().__init__(8)
            self.calls = 0

        def translate(self, rpng_description):
            self.calls += 1
            return super().translate(rpng_description)

    translator = CountingTranslator()
    schedule = 6 if custom == "compiler" else 8
    compiler = PlaquetteCompiler(
        "CUSTOM",
        (ChangeSchedulePass({i: i for i in range(schedule)} | {schedule: 10}),),
        lambda instructions: instructions,
    )
    selected_compiler = None if custom == "translator" else compiler
    selected_translator = None if custom == "compiler" else translator
    convention = Convention(
        "fixed_bulk",
        ConventionTriplet(
            FixedBulkCubeBuilder(selected_compiler, selected_translator),
            FixedBulkPipeBuilder(selected_compiler, selected_translator),
            FIXED_BULK_CONVENTION.triplet.observable_builder,
        ),
    )
    compiled = compile_block_graph(memory(), convention)
    assert (translator.calls > 0) == (custom != "compiler")
    tree = compiled.to_layer_tree()
    materialized = StimMaterializer().materialize_layer(tree._root._layer)
    layer = materialized.layer_sequence[0].layer_sequence[0]
    assert layer.measurement_schedule == (8 if custom == "translator" else 10)
    prefix = "ID(" if custom == "translator" else "CUSTOM("
    for child in layer.layers.values():
        assert all(p.name.startswith(prefix) for p in child.plaquettes.collection.values())
    circuit = compiled.generate_stim_circuit(1, database_path=None)
    circuit.detector_error_model()


def test_visualization_and_serialization_materialize_before_use() -> None:
    tree = compile_block_graph(memory()).to_layer_tree()
    svg_layers = tree.layers_to_svg(1)
    assert svg_layers and all("<svg" in svg for svg in svg_layers)
    assert tree.to_dict()["root"]["children"]
    url = tree.generate_crumble_url(1, detector_database=DetectorDatabase(), add_polygons=True)
    assert url.startswith("https://algassert.com/crumble#circuit=")
    root = tree._root
    tree._materialize_stim()
    assert tree._root is root


def test_bare_translation_and_identity_policy() -> None:
    description = RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    bare = DefaultRPNGTranslator().translate(description)
    identity = IdentityPlaquetteCompiler.compile(bare)
    assert bare.name == str(description)
    assert identity.name == f"ID({description})"
    assert bare.mergeable_instructions == (
        frozenset({"H"}) | MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES
    )
    assert identity.mergeable_instructions == (
        bare.mergeable_instructions | MEASUREMENT_INSTRUCTION_NAMES | RESET_INSTRUCTION_NAMES
    )
    assert identity.circuit == bare.circuit
    assert identity.debug_information == bare.debug_information


def test_stim_output_preserves_construction_tree() -> None:

    compiled = compile_block_graph(memory())
    tree = compiled.to_layer_tree()
    root = tree.construction_root
    node = tree._root
    observables = tuple(tree._abstract_observables)

    def specs(layer):
        if isinstance(layer, LayoutLayer):
            return [spec for child in layer.layers.values() for spec in specs(child)]
        if isinstance(layer, SequencedLayers):
            return [spec for child in layer.layer_sequence for spec in specs(child)]
        if isinstance(layer, RepeatedLayer):
            return specs(layer.internal_layer)
        assert isinstance(layer, SpecPlaquetteLayer)
        return [layer.specs]

    original_specs = specs(root)
    first = tree.generate_circuit(1, detector_database=DetectorDatabase(), database_path=None)
    second = tree.generate_circuit(2, detector_database=DetectorDatabase(), database_path=None)
    assert first == tree.generate_circuit(1, database_path=None)
    assert second.num_measurements > first.num_measurements
    assert tree.construction_root is root
    assert tree._root is node
    assert tree._stim_root is not node
    assert not node._annotations
    assert all(not child._annotations for child in node.children)
    assert specs(root) == original_specs
    assert tuple(tree._abstract_observables) == observables
    assert compiled.generate_stim_circuit(1, database_path=None) == first
    assert specs(compiled.to_layer_tree().construction_root) == original_specs


def test_detector_options_reach_stim_output(tmp_path) -> None:
    compiled = compile_block_graph(memory())
    without_detectors = compiled.generate_stim_circuit(1, manhattan_radius=0, database_path=None)
    assert without_detectors.num_detectors == 0
    assert without_detectors.num_observables == 1
    database = DetectorDatabase()
    path = tmp_path / "detectors.pkl"
    with_detectors = compiled.generate_stim_circuit(
        1, manhattan_radius=2, detector_database=database, database_path=path
    )
    assert with_detectors.num_detectors > 0
    assert len(database) > 0
    assert len(DetectorDatabase.from_file(path)) == len(database)
    loaded = compiled.generate_stim_circuit(1, database_path=path)
    assert loaded == with_detectors
