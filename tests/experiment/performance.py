# ruff: noqa: E402, PLC0415
"""Compare warm end-to-end compilation in separate, identically configured processes.

Usage: python tests/experiment/performance.py SOURCE_ROOT upstream|spec|direct K
Run from this experiment's root with its pinned Python environment.
"""

import cProfile
import importlib.util
import json
import pstats
import statistics
import sys
import time
import tracemalloc
from copy import deepcopy
from pathlib import Path

root, route, scale = sys.argv[1:]
sys.path.insert(0, str(Path(root) / "src"))
spec = importlib.util.spec_from_file_location("cases", Path(__file__).with_name("cases.py"))
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)
from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase


def run():
    """Compile the same memory graph through the selected QEC output route."""
    tree = compile_block_graph(cases.make_graph("memory_z")).to_layer_tree()
    if route == "spec":
        from tqec.compile.lowering.deltakit import DeltakitOptions, compile_to_deltakit

        return compile_to_deltakit(
            tree,
            int(scale),
            options=DeltakitOptions(annotation_mode="explicit", include_observables=True),
            export="stim",
        ).program
    return str(
        tree.generate_circuit(int(scale), detector_database=DetectorDatabase(), database_path=None)
    )


run()
timings = []
for _ in range(3):
    start = time.perf_counter()
    output = run()
    timings.append(time.perf_counter() - start)
tracemalloc.start()
run()
_, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
# A primitive clone isolates the change from C++ storage to Python native SSA.
if route != "spec":
    from tqec.circuit.moment import Moment

    if route == "direct":
        moment = Moment()
        moment.append("MX", [0, 1, 2, 3, 4])
    else:
        import stim

        moment = Moment(stim.Circuit("MX 0 1 2 3 4"))
    start = time.perf_counter()
    for _ in range(1000):
        deepcopy(moment)
    clone_us = (time.perf_counter() - start) * 1000
else:
    clone_us = None
profiler = cProfile.Profile()
profiler.runcall(run)
stats = pstats.Stats(profiler).stats  # ty: ignore[unresolved-attribute]
profile = sorted(
    [
        dict(
            file=path.split("site-packages/")[-1].split("/src/")[-1],
            function=function,
            inclusive_seconds=values[3],
            calls=values[1],
        )
        for (path, _, function), values in stats.items()
        if "tqec/" in path or "deltakit_compile/" in path or "xdsl/" in path
    ],
    key=lambda row: row["inclusive_seconds"],
    reverse=True,
)[:15]
print(
    json.dumps(
        dict(
            route=route,
            k=int(scale),
            seconds=timings,
            median_seconds=statistics.median(timings),
            peak_python_bytes=peak,
            clone_microseconds=clone_us,
            profile=profile,
            output_bytes=len(output.encode()),
        )
    )
)
