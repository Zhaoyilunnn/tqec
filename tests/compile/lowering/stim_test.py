from dataclasses import fields

import pytest

from tqec.compile.lowering.stim import StimMaterializer
from tqec.compile.specs.library.generators.extended_stabilizers import ExtendedPlaquetteCollection
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.extended_specs import ExtendedSpecCollection
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import RPNGPlaquetteSpec
from tqec.utils.enums import Basis, Orientation


@pytest.mark.parametrize("schedule", (6, 8))
@pytest.mark.parametrize("description", ("-x1- -x2- -x3- -x4-", "zx1z ---- zx3z ----"))
def test_rpng_materialization_is_exact(description: str, schedule: int) -> None:
    rpng = RPNGDescription.from_string(description)
    spec = RPNGPlaquetteSpec(rpng, schedule)
    lowering = StimMaterializer()
    actual = lowering.materialize_plaquette(spec)
    expected = DefaultRPNGTranslator(schedule).translate(rpng)
    assert actual.to_dict() == expected.to_dict()
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
            assert actual.num_moments == spec.num_moments


@pytest.mark.parametrize("orientation", tuple(Orientation))
def test_realignment_generator_round_trip(orientation) -> None:
    generator = FixedBulkConventionGenerator(DefaultRPNGTranslator(), IdentityPlaquetteCompiler)
    specs = generator.as_specs().get_temporal_hadamard_realignment_plaquettes(orientation)
    expected = generator.get_temporal_hadamard_realignment_plaquettes(orientation)
    lowering = StimMaterializer()
    for index, spec in specs.collection.items():
        assert lowering.materialize_plaquette(spec).to_dict() == expected[index].to_dict()
        assert spec.num_moments == expected[index].num_moments
