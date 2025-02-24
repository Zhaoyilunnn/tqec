"""Defines a high-level template composing several sub-templates:
:class:`LayoutTemplate`.

This module defines a :class:`~tqec.templates.base.Template` child class that
is able to represent several :class:`~tqec.templates.base.RectangularTemplate`
instances with the same scalable shape. Each of the managed
:class:`~tqec.templates.base.RectangularTemplate` instance is linked to a unique
2-dimensional position on an infinite 2-dimensional grid.

Example
-------

A grid of :math:`2 \\times 2` logical qubits can be represented with

.. code-block:: python

    from tqec.utils.position import BlockPosition2D
    from tqec.templates.layout import LayoutTemplate
    from tqec.templates.qubit import QubitTemplate

    qubit = QubitTemplate()
    grid = LayoutTemplate(
        {
            BlockPosition2D(0, 0): qubit,
            BlockPosition2D(0, 1): qubit,
            BlockPosition2D(1, 0): qubit,
            BlockPosition2D(1, 1): qubit,
        }
    )

Being a :class:`~tqec.templates.base.Template` instance, the above constructed
``grid`` can be displayed with

.. code-block:: python

    from tqec.templates.display import display_template

    display_template(qubit, 2)
    print("=" * 50)
    display_template(grid, 2)

which outputs

.. code-block:: text

    1   5   6   5   6   2
    7   9  10   9  10  11
    8  10   9  10   9  12
    7   9  10   9  10  11
    8  10   9  10   9  12
    3  13  14  13  14   4
    ==================================================
     1   5   6   5   6   2  29  33  34  33  34  30
     7   9  10   9  10  11  35  37  38  37  38  39
     8  10   9  10   9  12  36  38  37  38  37  40
     7   9  10   9  10  11  35  37  38  37  38  39
     8  10   9  10   9  12  36  38  37  38  37  40
     3  13  14  13  14   4  31  41  42  41  42  32
    15  19  20  19  20  16  43  47  48  47  48  44
    21  23  24  23  24  25  49  51  52  51  52  53
    22  24  23  24  23  26  50  52  51  52  51  54
    21  23  24  23  24  25  49  51  52  51  52  53
    22  24  23  24  23  26  50  52  51  52  51  54
    17  27  28  27  28  18  45  55  56  55  56  46
"""

from copy import deepcopy
from typing import Callable, Sequence

import numpy
import numpy.typing as npt
from typing_extensions import override

from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.templates.base import RectangularTemplate, Template
from tqec.utils.exceptions import TQECException
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import (
    BlockPosition2D,
    PlaquettePosition2D,
    PlaquetteShape2D,
    Shift2D,
)
from tqec.utils.scale import PlaquetteScalable2D


class LayoutTemplate(Template):
    def __init__(
        self,
        element_layout: dict[BlockPosition2D, RectangularTemplate],
        default_increments: Shift2D | None = None,
    ) -> None:
        """A template representing a layout of other templates.

        Each element template in the layout is placed at a specific position in
        the 2D grid.

        Note:
            The provided template positions have only one restriction: two
            templates should not be at the same position.
            In particular, this class does not require that the provided
            template are spatially connected or entirely cover a rectangular
            portion of the 2 spatial dimensions.

        Args:
            element_layout: a dictionary with the position of the element
                templates in the layout as keys and the templates as values.
            default_increments: default increments between two plaquettes. Defaults
                to ``Displacement(2, 2)`` when ``None``.
        """
        super().__init__(default_increments)
        if not element_layout:
            raise TQECException("Cannot create a layout with an empty template map.")

        scalable_shapes = {
            template.scalable_shape for template in element_layout.values()
        }
        if len(scalable_shapes) != 1:
            raise TQECException(
                "All templates in the layout should have the same scalable shape."
            )
        self._element_scalable_shape = scalable_shapes.pop()

        all_positions = list(element_layout.keys())
        min_x = min(position.x for position in all_positions)
        max_x = max(position.x for position in all_positions)
        min_y = min(position.y for position in all_positions)
        max_y = max(position.y for position in all_positions)
        # Shift the bounding box to the origin
        self._block_origin = BlockPosition2D(min_x, min_y)
        self._nx = max_x - min_x + 1
        self._ny = max_y - min_y + 1

        self._layout = deepcopy(element_layout)

    def get_indices_map_for_instantiation(
        self,
        instantiate_indices: Sequence[int] | None = None,
    ) -> dict[BlockPosition2D, dict[int, int]]:
        """Get one index map for each of the templates in the layout.

        This method is used internally by :meth:`LayoutTemplate.instantiate` and
        can be used externally to get a map from the instantiation indices used by
        each of the individual :class:`~tqec.templates.base.Template` instances
        stored in ``self`` to the global instantiation index used.

        Args:
            instantiate_indices: global indices used to instantiate ``self``.
                Have the same meaning and defaults as the ``plaquette_indices``
                parameter in :meth:`LayoutTemplate.instantiate`.
                Defaults to None.

        Returns:
            a map from positions to instantiation index maps. Each instantiation
            index map is a bijection from the template instantiation indices (going
            from ``1`` to ``template.expected_plaquettes_number``) to the global
            indices that are used in :meth:`LayoutTemplate.instantiate` (going
            from ``N`` to ``N + template.expected_plaquettes_number - 1`` where
            ``N`` depends on the other :class:`~tqec.templates.base.Template`
            instances managed by ``self``).
        """
        if instantiate_indices is None:
            instantiate_indices = list(range(1, self.expected_plaquettes_number + 1))
        index_count = 0
        indices_map: dict[BlockPosition2D, dict[int, int]] = {}
        for position, template in self._layout.items():
            indices_map[position] = {
                i + 1: instantiate_indices[i + index_count]
                for i in range(template.expected_plaquettes_number)
            }
            index_count += template.expected_plaquettes_number
        return indices_map

    def global_plaquettes_from_local_ones(
        self,
        local_plaquettes: dict[BlockPosition2D, Plaquettes],
        instantiate_indices: Sequence[int] | None = None,
    ) -> Plaquettes:
        different_positions = frozenset(self._layout.keys()).symmetric_difference(
            local_plaquettes.keys()
        )
        if different_positions:
            raise TQECException(
                "Expected one Plaquettes instance for EACH block in the layout "
                "but found the following position(s) that are not in both the "
                "provided local_plaquette and in the stored layout: "
                f"{different_positions}."
            )
        indices_maps = self.get_indices_map_for_instantiation(instantiate_indices)
        final_mapping: dict[int, Plaquette] = {}
        default_factories: list[Callable[[], Plaquette] | None] = []
        for position, plaquettes in local_plaquettes.items():
            index_map = indices_maps[position]
            collection = plaquettes.collection
            final_mapping.update(collection.map_keys(lambda i: index_map[i]))
            default_factories.append(collection.default_factory)
        # If all the factories are None, that is a valid merge and we can
        # early-return.
        if all(f is None for f in default_factories):
            return Plaquettes(FrozenDefaultDict(final_mapping, default_factory=None))
        if any(f is None for f in default_factories):
            raise TQECException(
                "Trying to merge Plaquettes instances with at least one having "
                "a default factory and another not having a default factory."
            )
        # We know for sure that all the factories are not None here.
        default_values = frozenset(f() for f in default_factories)  # type:ignore
        if len(default_values) > 1:
            raise TQECException(
                "Cannot merge Plaquettes instances with different default "
                "factories. Found factories returning different elements: "
                f"{default_values}."
            )
        return Plaquettes(
            FrozenDefaultDict(final_mapping, default_factory=default_factories[0])
        )

    @property
    @override
    def scalable_shape(self) -> PlaquetteScalable2D:
        """Returns a scalable version of the template shape."""
        return PlaquetteScalable2D(
            self._nx * self._element_scalable_shape.x,
            self._ny * self._element_scalable_shape.y,
        )

    def element_shape(self, k: int) -> PlaquetteShape2D:
        """Return the uniform shape of the element templates."""
        return self._element_scalable_shape.to_shape_2d(k)

    @property
    @override
    def expected_plaquettes_number(self) -> int:
        """Returns the number of plaquettes expected from the `instantiate`
        method.

        Returns:
            the number of plaquettes expected from the `instantiate` method.
        """
        return sum(
            template.expected_plaquettes_number for template in self._layout.values()
        )

    @override
    def instantiate(
        self, k: int, plaquette_indices: Sequence[int] | None = None
    ) -> npt.NDArray[numpy.int_]:
        """Generate the numpy array representing the template.

        Args:
            k: scaling parameter used to instantiate the template.
            plaquette_indices: the plaquette indices that will be forwarded to
                the underlying Template instance's instantiate method. Defaults
                to `range(1, self.expected_plaquettes_number + 1)` if `None`.

        Returns:
            a numpy array with the given plaquette indices arranged according to
            the underlying shape of the template.
        """
        indices_map = self.get_indices_map_for_instantiation(plaquette_indices)

        element_shape = self._element_scalable_shape.to_numpy_shape(k)
        ret = numpy.zeros(self.shape(k).to_numpy_shape(), dtype=numpy.int_)
        for pos, element in self._layout.items():
            imap = indices_map[pos]
            indices = [
                imap[i] for i in range(1, element.expected_plaquettes_number + 1)
            ]
            element_instantiation = element.instantiate(k, indices)
            shifted_pos = BlockPosition2D(
                pos.x - self._block_origin.x, pos.y - self._block_origin.y
            )
            ret[
                shifted_pos.y * element_shape[0] : (shifted_pos.y + 1)
                * element_shape[0],
                shifted_pos.x * element_shape[1] : (shifted_pos.x + 1)
                * element_shape[1],
            ] = element_instantiation
        return ret

    @override
    def instantiation_origin(self, k: int) -> PlaquettePosition2D:
        return self._block_origin.get_top_left_plaquette_position(self.element_shape(k))
