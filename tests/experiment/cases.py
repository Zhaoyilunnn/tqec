"""Exact output references captured before changing construction representation.

Regenerate deliberately with ``TQEC_UPDATE_BASELINES=1 uv run pytest -q
 tests/compile/decoupling_baseline_test.py`` on the recorded upstream commit.
"""

import hashlib
import json
import os
from pathlib import Path


from tqec.compile.compile import compile_block_graph
from tqec.compile.convention import (
    FIXED_BOUNDARY_CONVENTION,
    FIXED_BULK_CONVENTION,
    fixed_bulk_convention,
)
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
from tqec.computation.block_graph import BlockGraph
from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis
from tqec.utils.position import Position3D

CONVENTIONS = {
    "bulk": FIXED_BULK_CONVENTION,
    "diagonal": fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY),
    "boundary": FIXED_BOUNDARY_CONVENTION,
}
CASES = ("memory_x", "memory_z", "temporal", "spatial", "cnot", "junction", "hadamard")


def make_graph(case: str) -> BlockGraph:
    """Build small supported constructions, including extended stabilizers."""
    if case == "cnot":
        return cnot(Basis.Z)
    graph = BlockGraph(case)
    if case == "junction":
        center = graph.add_cube(Position3D(0, 0, 0), "ZZX")
        for position in ((0, 1, 0), (-1, 0, 0), (1, 0, 0)):
            graph.add_pipe(center, graph.add_cube(Position3D(*position), "ZZX"))
        return graph
    first = graph.add_cube(Position3D(0, 0, 0), "XZX" if case == "memory_x" else "XZZ")
    if case in ("temporal", "spatial", "hadamard"):
        position = Position3D(0, 1, 0) if case == "spatial" else Position3D(0, 0, 1)
        second = graph.add_cube(position, "ZXX" if case == "hadamard" else "XZZ")
        graph.add_pipe(first, second)
    return graph


