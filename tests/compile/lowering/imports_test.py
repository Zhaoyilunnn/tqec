"""Test compiler imports in a fresh interpreter without a physical backend."""

import subprocess
import sys
import textwrap


def test_compiler_and_layer_tree_do_not_import_stim() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
        import sys
        from importlib.abc import MetaPathFinder
        class NoBackend(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'stim', 'tqecd'}:
                    raise ModuleNotFoundError(fullname, name=fullname)
        sys.meta_path.insert(0, NoBackend())
        import tqec
        from tqec.plaquette.extended_specs import ExtendedSpecCollection
        from tqec.compile.convention import (
            FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION, fixed_bulk_convention,
        )
        from tqec.compile.specs.library.generators.schedules import DIAGONAL_SCHEDULE_FAMILY
        from tqec.gallery.cnot import cnot
        from tqec.utils.enums import Basis
        from tqec.utils.position import Position3D
        from tqec.utils.exceptions import TQECError
        for convention in (FIXED_BULK_CONVENTION, FIXED_BOUNDARY_CONVENTION,
                           fixed_bulk_convention(DIAGONAL_SCHEDULE_FAMILY)):
            for kind in ('memory', 'cnot', 'junction', 'hadamard'):
                graph = tqec.BlockGraph()
                if kind == 'cnot':
                    graph = cnot(Basis.Z)
                else:
                    first = graph.add_cube(Position3D(0,0,0),
                                           'ZZX' if kind == 'junction' else 'XZZ')
                    if kind == 'junction':
                        for xyz in ((0,1,0),(-1,0,0),(1,0,0)):
                            graph.add_pipe(first, graph.add_cube(Position3D(*xyz), 'ZZX'))
                    if kind == 'hadamard':
                        graph.add_pipe(first, graph.add_cube(Position3D(0,0,1), 'ZXX'))
                compiled = tqec.compile_block_graph(graph, convention)
                tree = compiled.to_layer_tree()
                assert tree._root._layer.scalable_timesteps is not None
        assert not any(m.split('.')[0] in {'stim', 'tqecd'} for m in sys.modules)
        for output in (lambda: compiled.generate_stim_circuit(1),
                       lambda: tree.generate_circuit(1),
                       lambda: tree.generate_crumble_url(1)):
            try:
                output()
            except TQECError as error:
                assert 'Stim output requires Stim and tqecd' in str(error)
            else:
                raise AssertionError('Missing backend did not fail')
    """),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
