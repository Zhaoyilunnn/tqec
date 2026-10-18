"""Materialize construction specifications using the existing Stim implementation."""

from tqec.compile.blocks.layers.atomic.layout import LayoutLayer
from tqec.compile.blocks.layers.atomic.plaquettes import PlaquetteLayer
from tqec.compile.blocks.layers.atomic.spec_plaquettes import SpecPlaquetteLayer
from tqec.compile.blocks.layers.composed.repeated import RepeatedLayer
from tqec.compile.blocks.layers.composed.sequenced import SequencedLayers
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.plaquette.spec import PlaquetteSpec, RPNGPlaquetteSpec
from tqec.utils.exceptions import TQECError


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
        else:
            raise TQECError(f"Stim lowering does not support {type(spec).__name__}.")
        self._plaquettes[spec] = result
        return result

    def materialize_layer(self, layer):
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
            return LayoutLayer(
                {pos: self.materialize_layer(child) for pos, child in layer.layers.items()},
                layer.element_shape,
            )
        if isinstance(layer, RepeatedLayer):
            return RepeatedLayer(self.materialize_layer(layer.internal_layer), layer.repetitions)
        if isinstance(layer, SequencedLayers):
            return type(layer)([self.materialize_layer(child) for child in layer.layer_sequence])
        return layer
