from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterable

from typing_extensions import override

from tqec.blocks.enums import SpatialBlockBorder, TemporalBlockBorder
from tqec.blocks.layers.atomic.base import BaseLayer
from tqec.blocks.layers.composed.base import BaseComposedLayer
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D


@dataclass
class RepeatedLayer(BaseComposedLayer):
    """Composed layer implementing repetition.

    This composed layer repeats another layer (that can be atomic or composed)
    multiple times.

    Attributes:
        layer: repeated layer.
        repetitions: number of repetitions to perform. Can scale with ``k``.
    """

    layer: BaseLayer | BaseComposedLayer
    repetitions: LinearFunction

    def __post_init__(self) -> None:
        # Check that the number of timesteps of self is a linear function.
        if self.layer.scalable_timesteps.slope != 0 and self.repetitions.slope != 0:
            raise TQECException(
                "Layers with a non-constant number of timesteps cannot be "
                "repeated a non-constant number of times as that would lead to "
                "a non-linear number of timesteps, which is not supported yet. "
                f"Got a layer with {self.layer.scalable_timesteps} timesteps "
                f"and tried to repeat it {self.repetitions} times."
            )

    @override
    def layers(self, k: int) -> Iterable[BaseLayer]:
        if isinstance(self.layer, BaseLayer):
            yield from (self.layer for _ in range(self.timesteps(k)))
        else:
            yield from itertools.chain.from_iterable(
                self.layer.layers(k) for _ in range(self.timesteps(k))
            )

    @property
    @override
    def scalable_timesteps(self) -> LinearFunction:
        if self.repetitions.slope == 0:
            return self.repetitions.offset * self.layer.scalable_timesteps
        else:
            return self.repetitions * self.layer.scalable_timesteps.offset

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        return self.layer.scalable_shape

    @override
    def with_spatial_borders_trimed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> RepeatedLayer:
        return RepeatedLayer(
            self.layer.with_spatial_borders_trimed(borders), self.repetitions
        )

    @override
    def with_temporal_borders_trimed(
        self, borders: Iterable[TemporalBlockBorder]
    ) -> RepeatedLayer | None:
        return RepeatedLayer(self.layer, self.repetitions - len(frozenset(borders)))
