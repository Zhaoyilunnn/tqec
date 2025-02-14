"""Block graph representation of a logical computation."""

from __future__ import annotations

from collections.abc import Mapping
import pathlib
from copy import deepcopy
from io import BytesIO
from typing import TYPE_CHECKING

from tqec.computation._base_graph import ComputationGraph
from tqec.computation.cube import Cube, CubeKind
from tqec.computation.pipe import Pipe, PipeKind
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Direction3D, SignedDirection3D

if TYPE_CHECKING:
    from tqec.interop.collada.html_viewer import _ColladaHTMLViewer
    from tqec.interop.pyzx.positioned import PositionedZX
    from tqec.computation.correlation import CorrelationSurface


BlockKind = CubeKind | PipeKind


class BlockGraph(ComputationGraph[Cube, Pipe]):
    """Block graph representation of a logical computation.

    A block graph consists of building blocks that fully define the boundary
    conditions and topological structures of a logical computation. It corresponds
    to the commonly used 3D spacetime diagram representation of a surface code
    logical computation.

    The graph contains two categories of blocks:

    1. :py:class:`~tqec.computation.cube.Cube`: The fundamental building blocks
    of the computation. A cube represents a block of quantum operations within
    a specific spacetime volume. These operations preserve or manipulate the
    quantum information encoded in the logical qubits. Cubes are represented
    as nodes in the graph.

    2. :py:class:`~tqec.computation.pipe.Pipe`: Connects cubes to form the
    topological structure representing the logical computation. A pipe occupies
    no spacetime volume and only replaces the operations within the cubes it
    connects. Pipes are represented as edges in the graph.
    """

    def add_edge(self, u: Cube, v: Cube, kind: PipeKind | None = None) -> None:
        """Add an edge to the graph. If the nodes of the edge do not exist in
        the graph, the nodes will be created and added to the graph.

        Args:
            u: The cube on one end of the edge.
            v: The cube on the other end of the edge.
            kind: The kind of the pipe connecting the cubes. If None, the kind will be
                automatically determined based on the cubes it connects to make the
                boundary conditions consistent. Default is None.

        Raises:
            TQECException: For each node in the edge, if there is already a node which is not
                equal to it at the same position, or the node is a port but there is already a
                different port with the same label in the graph.
        """
        if kind is None:
            pipe = Pipe.from_cubes(u, v)
        else:
            pipe = Pipe(u, v, kind)
        self._add_edge_and_nodes_with_checks(u, v, pipe)

    def validate(self) -> None:
        """Check the validity of the block graph to represent a logical
        computation.

        Refer to the Fig.9 in arXiv:2404.18369. Currently, we ignore the b) and e),
        only check the following conditions:

        - **No fanout:** ports can only have one pipe connected to them.
        - **Time-like Y:** Y cubes can only have time-like pipes connected to them.
        - **No 3D corner:** a cube cannot have pipes in all three directions.
        - **Match color at passthrough:** two pipes in a "pass-through" should have the same
          color orientation.
        - **Match color at turn:** two pipes in a "turn" should have the matching colors on
          faces that are touching.

        Raises:
            TQECException: If the above conditions are not satisfied.
        """
        for cube in self.nodes:
            self._validate_locally_at_cube(cube)

    def _validate_locally_at_cube(self, cube: Cube) -> None:
        """Check the validity of the block structures locally at a cube."""
        pipes = self.edges_at(cube.position)
        # a). no fanout
        if cube.is_port:
            if len(pipes) != 1:
                raise TQECException(
                    f"Port at {cube.position} does not have exactly one pipe connected."
                )
            return
        # c). time-like Y
        if cube.is_y_cube:
            if len(pipes) != 1:
                raise TQECException(
                    f"Y cube at {cube.position} does not have exactly one pipe connected."
                )
            if not pipes[0].direction == Direction3D.Z:
                raise TQECException(
                    f"Y cube at {cube.position} has non-timelike pipes connected."
                )
            return

        # Check the color matching conditions
        pipes_by_direction: dict[Direction3D, list[Pipe]] = {}
        for pipe in pipes:
            pipes_by_direction.setdefault(pipe.direction, []).append(pipe)
        # d), f), g). Match color
        for pipe in pipes:
            pipe.check_compatible_with_cubes()

    def to_zx_graph(self) -> PositionedZX:
        """Convert the block graph to a positioned PyZX graph.

        Returns:
            A :py:class:`~tqec.interop.pyzx.positioned.PositionedZX` object converted from the block graph.
        """
        from tqec.interop.pyzx.positioned import PositionedZX

        return PositionedZX.from_block_graph(self)

    def to_dae_file(
        self,
        file_path: str | pathlib.Path,
        pipe_length: float = 2.0,
        pop_faces_at_direction: SignedDirection3D | None = None,
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> None:
        """Write the block graph to a Collada DAE file.

        Args:
            file_path: The output file path.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_direction: Remove the faces at the given direction for all the blocks.
                This is useful for visualizing the internal structure of the blocks. Default is None.
            show_correlation_surface: The correlation surface to show in the block graph. Default is None.
        """
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file

        write_block_graph_to_dae_file(
            self,
            file_path,
            pipe_length,
            pop_faces_at_direction,
            show_correlation_surface,
        )

    @staticmethod
    def from_dae_file(filename: str | pathlib.Path, graph_name: str = "") -> BlockGraph:
        """Construct a block graph from a COLLADA DAE file.

        Args:
            filename: The input ``.dae`` file path.
            graph_name: The name of the block graph. Default is an empty string.

        Returns:
            The :py:class:`~tqec.computation.block_graph.BlockGraph` object constructed from the DAE file.
        """
        from tqec.interop.collada.read_write import read_block_graph_from_dae_file

        return read_block_graph_from_dae_file(filename, graph_name)

    def view_as_html(
        self,
        write_html_filepath: str | pathlib.Path | None = None,
        pipe_length: float = 2.0,
        pop_faces_at_direction: SignedDirection3D | None = None,
        show_correlation_surface: CorrelationSurface | None = None,
    ) -> _ColladaHTMLViewer:
        """View COLLADA model in html with the help of ``three.js``.

        This can display a COLLADA model interactively in IPython compatible environments.

        Args:
            write_html_filepath: The output html file path to write the generated html content
                if provided. Default is None.
            pipe_length: The length of the pipes. Default is 2.0.
            pop_faces_at_direction: Remove the faces at the given direction for all the blocks.
                This is useful for visualizing the internal structure of the blocks. Default is None.
            show_correlation_surface: The correlation surface to show in the block graph. Default is None.

        Returns:
            A helper class to display the 3D model, which implements the ``_repr_html_`` method and
            can be directly displayed in IPython compatible environments.
        """
        from tqec.interop.collada.html_viewer import display_collada_model
        from tqec.interop.collada.read_write import write_block_graph_to_dae_file

        bytes_buffer = BytesIO()
        write_block_graph_to_dae_file(
            self,
            bytes_buffer,
            pipe_length,
            pop_faces_at_direction,
            show_correlation_surface,
        )
        return display_collada_model(
            filepath_or_bytes=bytes_buffer.getvalue(),
            write_html_filepath=write_html_filepath,
        )

    def shift_min_z_to_zero(self) -> BlockGraph:
        """Shift the whole graph in the z direction to make the minimum z equal
        zero.

        Returns:
            A new graph with the minimum z position of the cubes equal to zero. The new graph
            will share no data with the original graph.
        """
        minz = min(cube.position.z for cube in self.nodes)
        if minz == 0:
            return deepcopy(self)
        new_graph = BlockGraph(self.name)
        for cube in self.nodes:
            new_graph.add_node(
                Cube(cube.position.shift_by(dz=-minz), cube.kind, cube.label)
            )
        for pipe in self.edges:
            u, v = pipe.u, pipe.v
            new_graph.add_edge(
                Cube(u.position.shift_by(dz=-minz), u.kind, u.label),
                Cube(v.position.shift_by(dz=-minz), v.kind, v.label),
                pipe.kind,
            )
        return new_graph

    def find_correlation_surfaces(self) -> list[CorrelationSurface]:
        """Find the correlation surfaces in the block graph.

        Returns:
            The list of correlation surfaces.
        """
        from tqec.interop.pyzx.correlation import find_correlation_surfaces

        zx_graph = self.to_zx_graph()

        return find_correlation_surfaces(zx_graph.g)

    def fill_ports(self, fill: Mapping[str, CubeKind] | CubeKind) -> None:
        """Fill the ports at specified positions with cubes of the given kind.

        Args:
            fill: A mapping from the label of the ports to the cube kind to fill.
                If a single kind is given, all the ports will be filled with the
                same kind.

        Raises:
            TQECException: if there is no port with the given label.
        """
        if isinstance(fill, CubeKind):
            fill = {label: fill for label in self._ports}
        for label, kind in fill.items():
            if label not in self._ports:
                raise TQECException(f"There is no port with label {label}.")
            pos = self._ports[label]
            fill_node = Cube(pos, kind)
            # Overwrite the node at the port position
            self._graph.add_node(pos, **{self._NODE_DATA_KEY: fill_node})
            for edge in self.edges_at(pos):
                self._graph.remove_edge(edge.u.position, edge.v.position)
                other = edge.u if edge.v.position == pos else edge.v
                self._graph.add_edge(
                    other.position,
                    pos,
                    **{self._EDGE_DATA_KEY: Pipe(other, fill_node, edge.kind)},
                )
            # Delete the port label
            self._ports.pop(label)

    def rotate(
        self,
        rotation_axis: Direction3D = Direction3D.Y,
        num_90_degree_rotation: int = 1,
        counterclockwise: bool = True,
    ) -> BlockGraph:
        """Rotate the graph around an axis by ``num_90_degree_rotation * 90``
        degrees and return a new rotated graph.

        Args:
            rotation_axis: The axis around which to rotate the graph.
            num_90_degree_rotation: The number of 90-degree rotations to apply to the graph.
            counterclockwise: Whether to rotate the graph counterclockwise. If set to False,
                the graph will be rotated clockwise. Defaults to True.

        Returns:
            A data-independent copy of the graph rotated by the given number of 90-degree rotations.
        """
        n = num_90_degree_rotation % 4

        if n == 0:
            return self.copy()
        g = self.to_zx_graph()
        rotated_g = g.rotate(rotation_axis, n, counterclockwise)
        return rotated_g.to_block_graph()
