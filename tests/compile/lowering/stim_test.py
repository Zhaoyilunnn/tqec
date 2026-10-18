from dataclasses import fields

import pytest

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.stim import StimMaterializer
from tqec.compile.specs.library.generators.extended_stabilizers import ExtendedPlaquetteCollection
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.extended_specs import ExtendedSpecCollection
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import PlaquetteSpecs, RPNGPlaquetteSpec
from tqec.templates.qubit import QubitTemplate
from tqec.utils.enums import Basis, Orientation
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D


@pytest.mark.parametrize("schedule", (6, 8))
@pytest.mark.parametrize("description", ("-x1- -x2- -x3- -x4-", "zx1z ---- zx3z ----"))
def test_rpng_materialization_is_exact(description: str, schedule: int) -> None:
    rpng = RPNGDescription.from_string(description)
    spec = RPNGPlaquetteSpec(rpng, schedule)
    lowering = StimMaterializer()
    actual = lowering.materialize_plaquette(spec)
    expected = DefaultRPNGTranslator(schedule).translate(rpng)
    assert actual.to_dict() == expected.to_dict()
    assert actual.circuit.qubits == spec.used_qubits
    assert actual.num_moments == spec.num_moments
    assert lowering.materialize_plaquette(spec) is actual
    moved = actual.reschedule_measurements(schedule + 2)
    assert actual.circuit == expected.circuit
    assert moved.circuit != actual.circuit


@pytest.mark.parametrize("reversed", (False, True))
@pytest.mark.parametrize("measurement", (None, Basis.Z))
@pytest.mark.parametrize("orientation", tuple(Orientation))
def test_all_extended_shapes_round_trip(reversed, measurement, orientation) -> None:
    specs = ExtendedSpecCollection.from_basis(
        Basis.X, None, measurement, reversed, orientation=orientation
    )
    concrete = ExtendedPlaquetteCollection.from_basis(
        Basis.X, None, measurement, reversed, orientation=orientation
    )
    lowering = StimMaterializer()
    for field in fields(specs):
        for half in ("top", "bottom"):
            spec = getattr(getattr(specs, field.name), half)
            expected = getattr(getattr(concrete, field.name), half)
            actual = lowering.materialize_plaquette(spec)
            assert actual.to_dict() == expected.to_dict()
            assert actual.circuit.qubits == spec.used_qubits
            assert actual.num_moments == spec.num_moments


@pytest.mark.parametrize("orientation", tuple(Orientation))
def test_realignment_generator_round_trip(orientation) -> None:
    generator = FixedBulkConventionGenerator(DefaultRPNGTranslator(), IdentityPlaquetteCompiler)
    specs = generator.as_specs().get_temporal_hadamard_realignment_plaquettes(orientation)
    expected = generator.get_temporal_hadamard_realignment_plaquettes(orientation)
    lowering = StimMaterializer()
    for index, spec in specs.collection.items():
        assert lowering.materialize_plaquette(spec).to_dict() == expected[index].to_dict()
        assert spec.used_qubits == expected[index].circuit.qubits
        assert spec.num_moments == expected[index].num_moments


def test_unsupported_layer_reports_backend_and_location() -> None:
    with pytest.raises(UnsupportedLoweringError) as caught:
        StimMaterializer().materialize_layer(object(), location=(2, "repeat"))
    assert caught.value.backend == "stim"
    assert caught.value.construction == "object"
    assert caught.value.location == (2, "repeat")


def test_alignment_policy_and_layout_footprint_before_lowering() -> None:

    description = RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    layer = SpecPlaquetteLayer(
        QubitTemplate(),
        PlaquetteSpecs(
            FrozenDefaultDict(
                {i: RPNGPlaquetteSpec(description, 6 if i % 2 else 8) for i in range(1, 15)}
            )
        ),
    )
    layout = LayoutLayer(
        {LayoutPosition2D.from_block_position(BlockPosition2D(0, 0)): layer}, layer.scalable_shape
    )
    lowered = StimMaterializer().materialize_layer(layout)
    assert layout.measurement_schedule == lowered.measurement_schedule == 8
    assert layout.qubits(1) == lowered.qubits(1)
    assert layout.qubits(2) == lowered.qubits(2)
    lowered.reschedule_measurements()
    assert all(
        p.num_moments == 9
        for child in lowered.layers.values()
        for p in child.plaquettes.collection.values()
    )
    assert layer.specs[1].num_moments == 7
