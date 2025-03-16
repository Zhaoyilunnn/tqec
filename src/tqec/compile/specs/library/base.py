from typing import Final

from tqec.compile.blocks.block import Block
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.specs.base import (
    BlockBuilderV2,
    CubeSpec,
)
from tqec.compile.specs.library.generators import (
    get_memory_qubit_plaquettes,
    get_memory_qubit_raw_template,
    get_spatial_cube_qubit_plaquettes,
    get_spatial_cube_qubit_raw_template,
)
from tqec.computation.cube import Port, YHalfCube, ZXCube
from tqec.plaquette.compilation.base import PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquettes
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.templates.base import RectangularTemplate
from tqec.templates.enums import ZObservableOrientation
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction


class BaseBlockBuilder(BlockBuilderV2):
    """Base implementation of the :class:`~tqec.compile.specs.base.BlockBuilder`
    interface.

    This class provides a good enough default implementation that should be
    enough for most of the block builders.
    """

    DEFAULT_BLOCK_REPETITIONS: Final[LinearFunction] = LinearFunction(2, -1)

    def __init__(self, compiler: PlaquetteCompiler) -> None:
        """Initialise the :class:`BaseBlockBuilder` with a compiler.

        Args:
            compiler: compiler to transform the plaquettes in the standard
                implementation to a custom implementation.
        """
        self._translator = DefaultRPNGTranslator()
        self._compiler = compiler

    @staticmethod
    def _get_template_and_plaquettes(
        spec: CubeSpec,
    ) -> tuple[
        RectangularTemplate,
        tuple[Plaquettes, Plaquettes, Plaquettes],
    ]:
        """Get the template and plaquettes corresponding to the provided ``spec``.

        Args:
            spec: specification of the cube we want to implement.

        Returns:
            the template and list of 3 mappings from plaquette indices to RPNG
            descriptions that are needed to implement the cube corresponding to
            the provided ``spec``.
        """
        assert isinstance(spec.kind, ZXCube)
        x, _, z = spec.kind.as_tuple()
        if not spec.is_spatial:
            orientation = (
                ZObservableOrientation.HORIZONTAL
                if x == Basis.Z
                else ZObservableOrientation.VERTICAL
            )
            return get_memory_qubit_raw_template(), (
                get_memory_qubit_plaquettes(orientation, z, None),
                get_memory_qubit_plaquettes(orientation, None, None),
                get_memory_qubit_plaquettes(orientation, None, z),
            )
        # else:
        return get_spatial_cube_qubit_raw_template(), (
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, z, None),
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, None),
            get_spatial_cube_qubit_plaquettes(x, spec.spatial_arms, None, z),
        )

    def __call__(self, spec: CubeSpec) -> Block:
        kind = spec.kind
        if isinstance(kind, Port):
            raise TQECException("Cannot build a block for a Port.")
        elif isinstance(kind, YHalfCube):
            raise NotImplementedError("Y cube is not implemented.")
        # else
        template, (init, repeat, measure) = (
            BaseBlockBuilder._get_template_and_plaquettes(spec)
        )
        layers = [
            PlaquetteLayer(template, init),
            RepeatedLayer(
                PlaquetteLayer(template, repeat),
                repetitions=BaseBlockBuilder.DEFAULT_BLOCK_REPETITIONS,
            ),
            PlaquetteLayer(template, measure),
        ]
        return Block(layers)
