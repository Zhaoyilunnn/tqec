from functools import partial

import pytest
import stim

from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import FIXED_BULK_CONVENTION, Convention, ConventionTriplet
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.lowering.stim import StimMaterializer
from tqec.compile.specs.library.fixed_bulk import FixedBulkCubeBuilder, FixedBulkPipeBuilder
from tqec.computation.block_graph import BlockGraph
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.plaquette.compilation.passes.scheduling import ChangeSchedulePass
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
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


def test_custom_translator_and_passes_are_preserved() -> None:
    class CountingTranslator(DefaultRPNGTranslator):
        def __init__(self):
            super().__init__(8)
            self.calls = 0

        def translate(self, rpng_description):
            self.calls += 1
            return super().translate(rpng_description)

    translator = CountingTranslator()
    compiler = PlaquetteCompiler(
        "CUSTOM",
        (ChangeSchedulePass({i: i for i in range(8)} | {8: 10}),),
        lambda instructions: instructions,
    )
    convention = Convention(
        "fixed_bulk",
        ConventionTriplet(
            FixedBulkCubeBuilder(compiler, translator),
            FixedBulkPipeBuilder(compiler, translator),
            FIXED_BULK_CONVENTION.triplet.observable_builder,
        ),
    )
    compiled = compile_block_graph(memory(), convention)
    assert translator.calls > 0
    tree = compiled.to_layer_tree()
    materialized = StimMaterializer().materialize_layer(tree._root._layer)
    layer = materialized.layer_sequence[0].layer_sequence[0]
    assert layer.measurement_schedule == 10
    for child in layer.layers.values():
        assert all(p.name.startswith("CUSTOM(") for p in child.plaquettes.collection.values())
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
