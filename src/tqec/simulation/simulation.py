import multiprocessing
from typing import Callable, Iterable, Iterator, Sequence

import sinter

from tqec.compile.deprecated.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.compile.specs.base import BlockBuilder, SubstitutionBuilder
from tqec.compile.specs.library.css import CSS_BLOCK_BUILDER, CSS_SUBSTITUTION_BUILDER
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import CorrelationSurface
from tqec.simulation.generation import generate_sinter_tasks
from tqec.utils.noise_model import NoiseModel


def start_simulation_using_sinter(
    block_graph: BlockGraph,
    ks: Sequence[int],
    ps: Sequence[float],
    noise_model_factory: Callable[[float], NoiseModel],
    manhattan_radius: int,
    block_builder: BlockBuilder = CSS_BLOCK_BUILDER,
    substitution_builder: SubstitutionBuilder = CSS_SUBSTITUTION_BUILDER,
    observables: list[CorrelationSurface] | None = None,
    detector_database: DetectorDatabase | None = None,
    num_workers: int = multiprocessing.cpu_count(),
    progress_callback: Callable[[sinter.Progress], None] | None = None,
    max_shots: int | None = None,
    max_errors: int | None = None,
    decoders: Iterable[str] = ("pymatching",),
    print_progress: bool = False,
    custom_decoders: dict[str, sinter.Decoder | sinter.Sampler] | None = None,
) -> Iterator[list[sinter.TaskStats]]:
    """Helper to run `stim` simulations using `sinter`.

    This function is the preferred entry-point to run `sinter` computations using
    `stim` from circuits generated by `tqec`.

    It removes the need to generate the `stim.Circuit` instances in parallel (due
    to the relative inefficiency of detector annotation at the moment) by
    importing and calling :func:`generate_sinter_tasks`. It also forwards
    several parameters to :func:`sinter.collect`, but without showing in its
    signature arguments that we do not envision using.

    Args:
        block_graph: a representation of the QEC computation to simulate.
        ks: values of the scaling parameter `k` to use in order to generate the
            circuits.
        ps: values of the noise parameter `p` to use to instantiate a noise
            model using the provided `noise_model_factory`.
        noise_model_factory: a callable that is used to instantiate a noise
            model from each of the noise parameters in `ps`.
        manhattan_radius: radius used to automatically compute detectors. The
            best value to set this argument to is the minimum integer such that
            flows generated from any given reset/measurement, from any plaquette
            at any spatial/temporal place in the QEC computation, do not
            propagate outside of the qubits used by plaquettes spatially located
            at maximum `manhattan_radius` plaquettes from the plaquette the
            reset/measurement belongs to (w.r.t. the Manhattan distance).
            Default to 2, which is sufficient for regular surface code. If
            negative, detectors are not computed automatically and are not added
            to the generated circuits.
        block_builder: A callable that specifies how to build the `CompiledBlock` from
            the specified `CubeSpecs`. Defaults to the block builder for the css type
            surface code.
        substitution_builder: A callable that specifies how to build the substitution
            plaquettes from the specified `PipeSpec`. Defaults to the substitution
            builder for the css type surface code.
        observables: a list of correlation surfaces to compile to logical
             observables and generate statistics for. If `None`, all the correlation
             surfaces of the provided computation are used.
        detector_database: an instance to retrieve from / store in detectors
            that are computed as part of the circuit generation.
        num_workers: The number of worker processes to use.
        progress_callback: Defaults to None (unused). If specified, then each
            time new sample statistics are acquired from a worker this method
            will be invoked with the new `sinter.TaskStats`.
        max_shots: Defaults to None (unused). Stops the sampling process
            after this many samples have been taken from the circuit.
        max_errors: Defaults to None (unused). Stops the sampling process
            after this many errors have been seen in samples taken from the
            circuit. The actual number sampled errors may be larger due to
            batching.
        decoders: Defaults to None (specified by each Task). The names of the
            decoders to use on each Task. It must either be the case that each
            Task specifies a decoder and this is set to None, or this is an
            iterable and each Task has its decoder set to None.
        print_progress: When True, progress is printed to stderr while
            collection runs.
        custom_decoders: Named child classes of `sinter.decoder`, that can be
            used if requested by name by a task or by the decoders list.
            If not specified, only decoders with support built into sinter, such
            as 'pymatching' and 'fusion_blossom', can be used.

    Yields:
        one simulation result (of type `list[sinter.TaskStats]`) per provided
        observable in `observables`.
    """
    if observables is None:
        observables = block_graph.find_correlation_surfaces()

    for i, correlation_surface in enumerate(observables):
        if print_progress:
            print(
                f"Generating statistics for observable {i + 1}/{len(observables)}",
                end="\r",
            )
        compiled_graph = compile_block_graph(
            block_graph,
            block_builder,
            substitution_builder,
            observables=[correlation_surface],
        )
        stats = sinter.collect(
            num_workers=num_workers,
            tasks=generate_sinter_tasks(
                compiled_graph,
                ks,
                ps,
                noise_model_factory,
                manhattan_radius,
                detector_database,
            ),
            progress_callback=progress_callback,
            max_shots=max_shots,
            max_errors=max_errors,
            decoders=decoders,
            print_progress=print_progress,
            custom_decoders=custom_decoders,
            hint_num_tasks=len(ks) * len(ps),
        )
        yield stats
