from unittest.mock import patch

import pytest

from tqec.compile.lowering.stim.compiler import IdentityPlaquetteCompiler
from tqec.compile.lowering.stim.translator import DefaultRPNGTranslator
from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.schedules import (
    DEFAULT_SCHEDULE_FAMILY,
    DIAGONAL_SCHEDULE_FAMILY,
)
from tqec.plaquette.spec import RPNGPlaquetteSpec
from tqec.plaquette.spec_mapper import PlaquetteSpecMapper
from tqec.utils.enums import Orientation


@pytest.mark.parametrize("schedule", (DEFAULT_SCHEDULE_FAMILY, DIAGONAL_SCHEDULE_FAMILY))
def test_spec_mapping_preserves_descriptions_without_translation(schedule) -> None:
    generator = FixedBulkConventionGenerator(
        DefaultRPNGTranslator(schedule.measurement_schedule),
        IdentityPlaquetteCompiler,
        schedule,
    )
    mapper = PlaquetteSpecMapper(schedule.measurement_schedule)
    descriptions = generator.get_memory_qubit_rpng_descriptions(Orientation.HORIZONTAL)
    with patch.object(DefaultRPNGTranslator, "translate", side_effect=AssertionError):
        specs = mapper(generator.get_memory_qubit_rpng_descriptions)(Orientation.HORIZONTAL)
    for index, description in descriptions.items():
        spec = specs[index]
        assert isinstance(spec, RPNGPlaquetteSpec)
        assert spec.description == description
        assert spec.measurement_schedule == schedule.measurement_schedule
    assert isinstance(specs.collection.default_value, RPNGPlaquetteSpec)
    assert specs.collection.default_value.description == descriptions.default_value
