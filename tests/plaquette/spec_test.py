from dataclasses import FrozenInstanceError

import pytest

from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.spec import PlaquetteSpecs, RPNGPlaquetteSpec
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict


def test_immutable_identity_and_collection_operations() -> None:
    empty = RPNGPlaquetteSpec(RPNGDescription.empty())
    other = RPNGPlaquetteSpec(RPNGDescription.empty(), measurement_schedule=8)
    original = PlaquetteSpecs(FrozenDefaultDict({1: empty}, default_value=empty))
    changed = original.with_updated_specs({1: other, 2: other})
    assert original[1] == empty
    assert changed[1] == other
    assert changed.without_specs({1})[1] == empty
    assert changed.map_indices(lambda i: i + 5)[6] == other
    assert changed.map_indices(lambda i: i + 5)[100] == empty
    assert hash(empty) == hash(RPNGPlaquetteSpec(RPNGDescription.empty()))
    assert empty != other
    with pytest.raises(FrozenInstanceError):
        setattr(empty, "measurement_schedule", 7)
    with pytest.raises(TQECError, match="Index 0"):
        original.map_indices(lambda _: 0)
