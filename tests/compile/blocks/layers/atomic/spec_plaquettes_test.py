from unittest.mock import patch

from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.positioning import LayoutPosition2D
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import PlaquetteSpecs, RPNGPlaquetteSpec
from tqec.templates.qubit import QubitTemplate
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import BlockPosition2D


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


def test_layout_uses_identical_mapping_for_specs() -> None:

    description = RPNGDescription.from_string("-z1- -z2- -z3- -z4-")
    spec = RPNGPlaquetteSpec(description)
    plaquette = DefaultRPNGTranslator().translate(description)
    template = QubitTemplate()
    specs = PlaquetteSpecs(FrozenDefaultDict({i: spec for i in range(1, 15)}))
    concrete = Plaquettes(specs.collection.map_values(lambda _: plaquette))
    positions = [LayoutPosition2D.from_block_position(BlockPosition2D(i, 0)) for i in (0, 1)]
    spec_layer = SpecPlaquetteLayer(template, specs)
    layout = LayoutLayer({p: spec_layer for p in positions}, spec_layer.scalable_shape)
    old = LayoutLayer(
        {p: PlaquetteLayer(template, concrete) for p in positions}, spec_layer.scalable_shape
    )
    merged_template, merged = layout.to_template_and_specs()
    old_template, old_merged = old.to_template_and_plaquettes()
    assert (merged_template.instantiate(2) == old_template.instantiate(2)).all()
    assert set(merged.collection) == set(old_merged.collection)
    assert all(item == spec for item in merged.collection.values())
