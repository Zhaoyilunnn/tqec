"""Apply existing template indexing and seam substitutions before text emission."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.extended import extended_operations
from tqec.compile.lowering.bloq.realignment import realignment_operations
from tqec.compile.lowering.bloq.rpng import rpng_operations
from tqec.compile.lowering.bloq.schedule import merge_moment
from tqec.plaquette.spec import ExtendedPlaquetteSpec, RealignmentPlaquetteSpec, RPNGPlaquetteSpec
from tqec.utils.enums import Orientation


def layout_moments(layer: LayoutLayer, k: int, reschedule: bool, location: tuple) -> list[list]:
    """Expand a complete spatial slice using its resolved plaquette collection."""
    if not all(isinstance(child, SpecPlaquetteLayer) for child in layer.layers.values()):
        raise UnsupportedLoweringError(
            "bloq", "concrete layer", "requires construction specs", location
        )
    template, specs = layer.to_template_and_specs()
    increments = template.get_increments()
    minimum, _ = layer.bounds
    shape = layer.element_shape.to_shape_2d(k)
    shift = (minimum.x * (shape.x - 1), minimum.y * (shape.y - 1))
    moments: dict = {}
    for row, indices in enumerate(template.instantiate(k).tolist()):
        for col, index in enumerate(indices):
            if not index:
                continue
            spec = specs[index]
            if isinstance(spec, RPNGPlaquetteSpec):
                local = rpng_operations(spec)
            elif isinstance(spec, ExtendedPlaquetteSpec):
                local = extended_operations(spec)
            elif isinstance(spec, RealignmentPlaquetteSpec):
                local = realignment_operations(spec)
            else:
                raise UnsupportedLoweringError(
                    "bloq", type(spec).__name__, "unknown spec", (*location, row, col)
                )
            dx = spec.origin.x + col * increments.x + shift[0]
            dy = spec.origin.y + row * increments.y + shift[1]
            for timestep, operations in local.items():
                for gate, targets in operations:
                    t = (
                        layer.measurement_schedule
                        if reschedule and gate.startswith("M")
                        else timestep
                    )
                    moments.setdefault(t, []).append(
                        (gate, tuple((x + dx, y + dy) for x, y in targets))
                    )
            # Empty trailing moments are significant for aligned spatial slices.
            moments.setdefault(max(local), [])
    return [
        merge_moment(moments.get(t, []), (*location, t)) for t in range(max(moments, default=0) + 1)
    ]


def detector_regions(layer: LayoutLayer, k: int, radius: int = 2):
    """Locate construction-owned checks in the existing plaquette neighborhood.

    The radius is measured in template cells, as in TQEC detector finding. A
    closed global relation spanning a logical correlation surface is not a local
    syndrome check, even if its noiseless parity is deterministic.
    """
    template, specs = layer.to_template_and_specs()
    increments = template.get_increments()
    minimum, _ = layer.bounds
    shape = layer.element_shape.to_shape_2d(k)
    shift = (minimum.x * (shape.x - 1), minimum.y * (shape.y - 1))
    for row, indices in enumerate(template.instantiate(k).tolist()):
        for col, index in enumerate(indices):
            if not index:
                continue
            spec = specs[index]
            center = (
                spec.origin.x + col * increments.x + shift[0],
                spec.origin.y + row * increments.y + shift[1],
            )
            syndrome = {center}
            if isinstance(spec, ExtendedPlaquetteSpec):
                side = 1 if spec.second else -1
                other = (
                    ((-1, -side), (1, -side))
                    if spec.orientation == Orientation.VERTICAL
                    else ((-side, -1), (-side, 1))
                )
                dx, dy = other[spec.is_reversed]
                syndrome.add((center[0] + dx, center[1] + dy))
            yield center, (radius * increments.x + 1, radius * increments.y + 1), syndrome
