import pytest

from tqec.compile.lowering.stim import StimMaterializer
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import RPNGPlaquetteSpec


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
