"""Concrete Stim plaquettes arranged on a scalable template."""

from tqec.compile.blocks.layers.atomic.template import TemplateLayer
from tqec.plaquette.plaquette import Plaquettes


class PlaquetteLayer(TemplateLayer[Plaquettes]):
    """Store a template and materialized plaquettes for Stim circuit generation."""
