from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Final, Iterable, TypeGuard

from typing_extensions import override

from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.compile.blocks.enums import SpatialBlockBorder
from tqec.compile.blocks.layers.atomic.base import BaseLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.positioning import (
    LayoutCubePosition2D,
    LayoutPipePosition2D,
    LayoutPosition2D,
)
from tqec.compile.generation import generate_circuit
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.enums import TemplateBorder
from tqec.templates.layout import LayoutTemplate
from tqec.utils.exceptions import TQECException
from tqec.utils.position import BlockPosition2D, Direction3D, Shift2D
from tqec.utils.scale import PhysicalQubitScalable2D

DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER: Final[int] = 1
"""Default number of qubits that are shared between two neighbouring layers."""


def contains_only_plaquette_layers(
    layers: dict[LayoutPosition2D, BaseLayer],
) -> TypeGuard[dict[LayoutPosition2D, PlaquetteLayer]]:
    return all(isinstance(layer, PlaquetteLayer) for layer in layers.values())


@dataclass(frozen=True)
class LayoutLayer(BaseLayer):
    """A layer gluing several other layers together on a 2-dimensional grid."""

    layers: dict[LayoutPosition2D, BaseLayer]
    element_shape: PhysicalQubitScalable2D

    def __post_init__(self) -> None:
        if not self.layers:
            raise TQECException(
                f"An instance of {type(self).__name__} should have at least one layer."
            )

    @cached_property
    def bounds(self) -> tuple[BlockPosition2D, BlockPosition2D]:
        xs = [pos._x for pos in self.layers.keys()]
        ys = [pos._y for pos in self.layers.keys()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        # We know for sure that the minima and maxima above are located on cube
        # positions and so are multiples of 2.
        return (
            BlockPosition2D(minx // 2, miny // 2),
            BlockPosition2D(maxx // 2, maxy // 2),
        )

    @property
    @override
    def scalable_shape(self) -> PhysicalQubitScalable2D:
        xs = [pos._x for pos in self.layers.keys()]
        ys = [pos._y for pos in self.layers.keys()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        shapex, shapey = (maxx - minx) // 2 + 1, (maxy - miny) // 2 + 1
        return PhysicalQubitScalable2D(
            shapex * (self.element_shape.x - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
            shapey * (self.element_shape.y - DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER)
            + DEFAULT_SHARED_QUBIT_DEPTH_AT_BORDER,
        )

    @override
    def with_spatial_borders_trimmed(
        self, borders: Iterable[SpatialBlockBorder]
    ) -> LayoutLayer:
        raise TQECException(
            f"Cannot trim spatial borders of a {type(self).__name__} instance."
        )

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, LayoutLayer)
            and self.element_shape == value.element_shape
            and self.layers == value.layers
        )

    def to_template_and_plaquettes(self) -> tuple[LayoutTemplate, Plaquettes]:
        """Return an equivalent representation of ``self`` with a template and some
        plaquettes.

        Raises:
            NotImplementedError: if not all layers composing ``self`` are instances
                of :class:`~tqec.compile.blocks.layers.atomic.plaquette.PlaquetteLayer`.

        Returns:
            a tuple ``(template, plaquettes)`` that is ready to be used with
            :meth:`~tqec.compile.generation.generate_circuit` to obtain the quantum
            circuit representing ``self``.
        """
        if not contains_only_plaquette_layers(self.layers):
            raise NotImplementedError(
                f"Found a layer that is not an instance of {PlaquetteLayer.__name__}. "
                "Detector computation is not implemented (yet) for this case."
            )
        cubes: dict[BlockPosition2D, PlaquetteLayer] = {
            pos.to_block_position(): layer
            for pos, layer in self.layers.items()
            if isinstance(pos, LayoutCubePosition2D)
        }
        template_dict: Final = {pos: layer.template for pos, layer in cubes.items()}
        plaquettes_dict = {pos: layer.plaquettes for pos, layer in cubes.items()}

        # Add plaquettes from each pipe to the plaquette_dict.
        pipes: dict[tuple[BlockPosition2D, BlockPosition2D], PlaquetteLayer] = {
            pos.to_pipe(): layer
            for pos, layer in self.layers.items()
            if isinstance(pos, LayoutPipePosition2D)
        }
        for (u, v), pipe_layer in pipes.items():
            pipe_direction = Direction3D.from_neighbouring_positions(
                u.to_3d(), v.to_3d()
            )
            u_border: TemplateBorder
            v_border: TemplateBorder
            match pipe_direction:
                case Direction3D.X:
                    u_border, v_border = TemplateBorder.LEFT, TemplateBorder.RIGHT
                case Direction3D.Y:
                    # TODO: check that this is the correct order.
                    u_border, v_border = TemplateBorder.BOTTOM, TemplateBorder.TOP
                case Direction3D.Z:
                    raise TQECException("Should not happen. This is a logical error.")

            # Updating plaquettes in plaquettes_dict
            for pos, (cube_border, pipe_border) in [
                (u, (v_border, u_border)),
                (v, (u_border, v_border)),
            ]:
                plaquette_indices_mapping = pipe_layer.template.get_border_indices(
                    pipe_border
                ).to(template_dict[pos].get_border_indices(cube_border))
                plaquettes_dict[pos] = plaquettes_dict[pos].with_updated_plaquettes(
                    {
                        plaquette_indices_mapping[pipe_plaquette_index]: plaquette
                        for pipe_plaquette_index, plaquette in pipe_layer.plaquettes.collection.items()
                        # Filtering only plaquette indices that are on the side we are
                        # interested in.
                        if pipe_plaquette_index in plaquette_indices_mapping
                    }
                )

        template = LayoutTemplate(template_dict)
        return template, template.get_global_plaquettes(plaquettes_dict)

    def to_circuit(self, k: int) -> ScheduledCircuit:
        """Return the quantum circuit representing the layer.

        Args:
            k: scaling factor.

        Returns:
            quantum circuit representing the layer.
        """
        template, plaquettes = self.to_template_and_plaquettes()
        scheduled_circuit = generate_circuit(template, k, plaquettes)
        # Shift the qubits of the returned scheduled circuit
        mincube, _ = self.bounds
        eshape = self.element_shape.to_shape_2d(k)
        shift = Shift2D(mincube.x * eshape.x, mincube.y * eshape.y)
        shifted_circuit = scheduled_circuit.map_to_qubits(lambda q: q + shift)
        return shifted_circuit
