"""Local syndrome ownership in resolved construction layouts."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.plaquette.spec import ExtendedPlaquetteSpec
from tqec.utils.enums import Orientation


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
