from unittest.mock import patch

import pytest

from tqec.compile.specs.library.generators.fixed_bulk import FixedBulkConventionGenerator
from tqec.compile.specs.library.generators.schedules import (
    DEFAULT_SCHEDULE_FAMILY,
    DIAGONAL_SCHEDULE_FAMILY,
)
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
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
        assert specs[index].description == description
        assert specs[index].measurement_schedule == schedule.measurement_schedule
    assert specs.collection.default_value.description == descriptions.default_value
