"""Description-building entry point shared by the built-in builders."""

from copy import copy
from functools import cache
from typing import Any, cast


class SpecificationBuilder:
    @cache
    def build_specs(self, spec, block_temporal_height):
        """Reuse the builder's structural algorithm with a description generator.

        A custom physical translator or compiler retains the legacy Stim path.
        No policy supplied by the caller is replaced with a built-in default.
        """
        builder = cast(Any, copy(self))
        builder._generator = builder._generator.as_specs()
        return builder(spec, block_temporal_height)
