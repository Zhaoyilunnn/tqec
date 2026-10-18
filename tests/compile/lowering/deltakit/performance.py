"""Print reproducible native-backend profiles; run as a module from the repository."""

import cProfile
import json
import pstats
import time
import tracemalloc
from typing import Literal

from tests.compile.decoupling_baseline_test import make_graph
from tqec.compile.compile import compile_block_graph
from tqec.compile.lowering.deltakit import DeltakitOptions, compile_to_deltakit


def report(case: str, k: int, mode: Literal["explicit", "auto"]) -> dict:
    """Measure native export and inclusive time in identifiable compiler functions."""
    tree = compile_block_graph(make_graph(case)).to_layer_tree()
    options = DeltakitOptions(annotation_mode=mode, include_observables=mode != "auto")
    profiler = cProfile.Profile()
    tracemalloc.start()
    start = time.perf_counter()
    profiler.enable()
    result = compile_to_deltakit(tree, k, options=options, export="stim")
    profiler.disable()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    buckets = {
        "template_instantiation": ("/templates/", {"instantiate"}),
        "plaquette_translation": (
            "/lowering/deltakit/",
            {"rpng_operations", "extended_operations", "realignment_operations"},
        ),
        "schedule_merge": ("/lowering/deltakit/", {"merge_moment"}),
        "native_fragment_and_flow_build": ("/lowering/deltakit/", {"build_fragment"}),
        "explicit_detector_relations": ("/lowering/deltakit/", {"detector_recipes"}),
        "native_passes_and_export": ("/frontend/logical_assembler.py", {"compile"}),
        "native_detector_finding": ("/stabiliser/find_detectors.py", {"apply"}),
        "native_stim_lowering": ("/stim/lower_physical_to_stim.py", {"apply"}),
    }
    stats = pstats.Stats(profiler).stats  # ty: ignore[unresolved-attribute]
    timings = {
        name: sum(
            value[3]
            for (path, _, function), value in stats.items()
            if fragment in path and function in functions
        )
        for name, (fragment, functions) in buckets.items()
    }
    return {
        "case": case,
        "k": k,
        "mode": mode,
        "wall_seconds": elapsed,
        "peak_python_bytes": peak,
        "text_bytes": len(result.program.encode()),
        "inclusive_seconds": timings,
    }


if __name__ == "__main__":
    for arguments in (
        ("memory_z", 1, "explicit"),
        ("memory_z", 2, "explicit"),
        ("memory_z", 1, "auto"),
    ):
        print(json.dumps(report(*arguments)), flush=True)
