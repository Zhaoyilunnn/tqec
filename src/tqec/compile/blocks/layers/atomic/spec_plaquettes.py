"""Scalable layers containing physical construction descriptions."""

from tqec.compile.blocks.layers.atomic.template import TemplateLayer
from tqec.plaquette.spec import PlaquetteSpecs


class SpecPlaquetteLayer(TemplateLayer[PlaquetteSpecs]):
    """Store a template and descriptions without constructing physical circuits."""

    @property
    def specs(self) -> PlaquetteSpecs:
        """Return the immutable descriptions indexed by the template."""
        return self.plaquettes
