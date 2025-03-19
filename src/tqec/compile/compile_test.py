import itertools

import pytest

from tqec.compile.compile import compile_block_graph_v2
from tqec.compile.specs.base import (
    BlockBuilder,
    CubeBuilder,
    PipeBuilder,
    SubstitutionBuilder,
)
from tqec.compile.specs.library.css import CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER
from tqec.compile.specs.library.standard import (
    STANDARD_CUBE_BUILDER,
    STANDARD_PIPE_BUILDER,
)
from tqec.compile.specs.library.zxxz import (
    ZXXZ_BLOCK_BUILDER,
    ZXXZ_SUBSTITUTION_BUILDER,
)
from tqec.computation.block_graph import BlockGraph
from tqec.utils.noise_model import NoiseModel
from tqec.utils.position import Position3D

SPECS: dict[str, tuple[BlockBuilder, SubstitutionBuilder]] = {
    "CSS": (CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER),
    "ZXXZ": (ZXXZ_BLOCK_BUILDER, ZXXZ_SUBSTITUTION_BUILDER),
}


STANDARD_SPECS: dict[str, tuple[CubeBuilder, PipeBuilder]] = {
    "STANDARD": (STANDARD_CUBE_BUILDER, STANDARD_PIPE_BUILDER)
}


@pytest.mark.parametrize(
    ("spec", "kind", "k"),
    itertools.product(STANDARD_SPECS.keys(), ("ZXZ", "ZXX", "XZX", "XZZ"), (1,)),
)
def test_compile_two_same_blocks_connected_in_time(
    spec: str, kind: str, k: int
) -> None:
    d = 2 * k + 1
    g = BlockGraph("Two Same Blocks in Time Experiment")
    # FIXME: position (1,1,0) and (1,1,1) not working
    # p1 = Position3D(1, 1, 0)
    # p2 = Position3D(1, 1, 1)
    p1 = Position3D(0, 0, 0)
    p2 = Position3D(0, 0, 1)
    g.add_cube(p1, kind)
    g.add_cube(p2, kind)
    g.add_pipe(p1, p2)

    cube_builder, pipe_builder = STANDARD_SPECS[spec]
    correlation_surfaces = g.find_correlation_surfaces()
    assert len(correlation_surfaces) == 1
    compiled_graph = compile_block_graph_v2(
        g, cube_builder, pipe_builder, correlation_surfaces
    )

    circuit = compiled_graph.generate_stim_circuit(
        k, noise_model=NoiseModel.uniform_depolarizing(0.001), manhattan_radius=2
    )

    dem = circuit.detector_error_model()
    assert dem.num_detectors == (d**2 - 1) * 2 * d
    assert dem.num_observables == 1
    assert len(dem.shortest_graphlike_error()) == d
