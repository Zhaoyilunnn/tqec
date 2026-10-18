from unittest.mock import patch

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import PlaquetteSpecs, RPNGPlaquetteSpec
from tqec.templates.qubit import QubitTemplate
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def test_layer_geometry_and_timing_match_concrete_layer() -> None:
    description = RPNGDescription.from_string("-x1- -x2- -x3- -x4-")
    concrete = PlaquetteLayer(
        QubitTemplate(),
        Plaquettes(
            FrozenDefaultDict(
                {i: DefaultRPNGTranslator().translate(description) for i in range(1, 15)}
            )
        ),
    )
    with patch.object(DefaultRPNGTranslator, "translate", side_effect=AssertionError):
        layer = SpecPlaquetteLayer(
            QubitTemplate(),
            PlaquetteSpecs(
                FrozenDefaultDict({i: RPNGPlaquetteSpec(description) for i in range(1, 15)})
            ),
        )
        assert layer.scalable_shape == concrete.scalable_shape
        assert layer.scalable_num_moments == concrete.scalable_num_moments
        for border in SpatialBlockBorder:
            trimmed = layer.with_spatial_borders_trimmed([border])
            old_trimmed = concrete.with_spatial_borders_trimmed([border])
            assert isinstance(trimmed, SpecPlaquetteLayer)
            assert trimmed.scalable_shape == old_trimmed.scalable_shape
            assert set(trimmed.specs.collection) == set(old_trimmed.plaquettes.collection)
