"""Materialize construction specifications using the existing Stim implementation."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.raw import RawCircuitLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.specs.library.generators.extended_stabilizers import ExtendedPlaquetteCollection
from tqec.compile.specs.library.generators.fixed_bulk import make_fixed_bulk_realignment_plaquette
from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import (
    ExtendedPlaquetteSpec,
    PlaquetteSpec,
    RealignmentPlaquetteSpec,
    RPNGPlaquetteSpec,
)


class StimMaterializer:
    def __init__(self) -> None:
        """Keep materialized plaquettes local to a single lowering operation."""
        self._plaquettes: dict[PlaquetteSpec, Plaquette] = {}
        self._translators: dict[int, DefaultRPNGTranslator] = {}

    def materialize_plaquette(self, spec: PlaquetteSpec) -> Plaquette:
        """Build a concrete plaquette, preserving its original name and debug data."""
        if spec in self._plaquettes:
            return self._plaquettes[spec]
        if isinstance(spec, RPNGPlaquetteSpec):
            translator = self._translators.setdefault(
                spec.measurement_schedule, DefaultRPNGTranslator(spec.measurement_schedule)
            )
            result = translator.translate(spec.description)
            if spec.compiled:
                result = IdentityPlaquetteCompiler.compile(result)
        elif isinstance(spec, ExtendedPlaquetteSpec):
            collection = ExtendedPlaquetteCollection.from_description(
                spec.description,
                spec.reset,
                spec.measurement,
                spec.is_reversed,
                spec.orientation,
                spec.data_operations,
            )
            pair = getattr(collection, spec.shape)
            result = pair.bottom if spec.second else pair.top
        elif isinstance(spec, RealignmentPlaquetteSpec):
            result = make_fixed_bulk_realignment_plaquette(
                spec.stabilizer_basis,
                spec.z_orientation,
                spec.mq_reset,
                spec.mq_measurement,
                spec.debug_basis,
            )
            if spec.boundary is not None:
                result = result.project_on_boundary(spec.boundary)
        else:
            raise UnsupportedLoweringError(
                "stim", type(spec).__name__, "unknown plaquette specification"
            )
        self._plaquettes[spec] = result
        return result

    def materialize_layer(self, layer, *, location: tuple = ()):  # noqa: PLR0911
        """Preserve geometry and repetition while replacing specs with concrete plaquettes.

        Existing concrete layers, including RawCircuitLayer, are legacy Stim-only
        inputs and remain available to custom conventions.
        """
        if isinstance(layer, SpecPlaquetteLayer):
            return PlaquetteLayer(
                layer.template,
                Plaquettes(layer.specs.collection.map_values(self.materialize_plaquette)),
                layer.trimmed_spatial_borders,
            )
        if isinstance(layer, LayoutLayer):
            children = {
                pos: self.materialize_layer(child, location=(*location, pos))
                for pos, child in layer.layers.items()
            }
            if all(children[pos] is child for pos, child in layer.layers.items()):
                return layer
            return LayoutLayer(children, layer.element_shape)
        if isinstance(layer, RepeatedLayer):
            child = self.materialize_layer(layer.internal_layer, location=(*location, "repeat"))
            return (
                layer if child is layer.internal_layer else RepeatedLayer(child, layer.repetitions)
            )
        if isinstance(layer, SequencedLayers):
            children = [
                self.materialize_layer(child, location=(*location, i))
                for i, child in enumerate(layer.layer_sequence)
            ]
            if all(child is original for child, original in zip(children, layer.layer_sequence)):
                return layer
            return type(layer)(children)
        if isinstance(layer, (PlaquetteLayer, RawCircuitLayer)):
            return layer
        raise UnsupportedLoweringError("stim", type(layer).__name__, "unknown layer type", location)
