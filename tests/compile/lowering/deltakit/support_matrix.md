# Deltakit support matrix

Pinned source and reproduction commands are in [README.md](README.md).
“Supported” describes the cases and scales listed here, not arbitrary graphs.

| Construction | Convention and scale | Physical output | Explicit QEC | Native auto |
|---|---|---|---|---|
| X memory and Z memory | Bulk, diagonal bulk, boundary; k=1,2 | Supported | Supported; distance 3,5 | Experimental; bulk k=1,2 has one extra independent constraint |
| Temporal pipe and spatial pipe | All three; k=1,2 | Supported | Supported; spatial distance 3,5 | Untested |
| CNOT and three-arm junction | All three; k=1,2 | Supported | Supported | Untested |
| Temporal Hadamard | All three; k=1,2 | Supported | Supported | Untested |
| Shifted spatial pipe with negative coordinates | All three; k=1 | Supported | Supported | Untested |
| Independent temporal Hadamard beside another readout | Bulk; k=1 | Supported | Supported | Untested |
| Move and rotation, three CNOTs, two disconnected temporal components | Bulk; k=1 | Supported | Supported | Untested |
| Unrescheduled boundary junction | Boundary; k=1 | Supported in physical-only mode | Unsupported: duplicate measurement in one slice | Untested |
| Spatial Hadamard with known baseline failures | Any | Not claimed | Not claimed | Untested |
| Concrete Stim plaquettes, custom unknown specs | Any | Rejected | Rejected | Rejected |
| Dynamic control and native loops | Any | Unsupported | Unsupported | Unsupported |

Physical comparisons include each gate's time and coordinates, measurement count,
and the declared qubit footprint. Explicit QEC comparisons check detector rank
and union span, logical measurement parities and noiseless determinism. Equal
logical parities also imply equal response to every measurement-record flip;
this comparison includes every observable ID, not only the number of observables.
No general matching-decoder performance claim is made.

Local tests cover RPNG schedules and Y bases, extended stabilizer shapes in both
orientations and schedule directions, data reset and measurement variants, and
realignment boundary projections. Native flow verification samples creation and
destruction relations; independent signed algebra checks every declared relation.

Repeated slices are bounded and unrolled. Fragment definitions are reused before
assembly. Default limits are 1,000 slices, 100,000 cells and 2,048 qubits; these are
allocation guards, not validated maximum problem sizes. Signed closed detectors
that need a constant correction are rejected. The backend preserves their sign
internally and never silently drops or flips such a constraint.

The explicit mode uses locally proven detectors and exports native flow contracts.
Running the entire automatic flow pipeline on that output is not a supported
configuration. Auto output intentionally requires omitting logical observables
and is marked `experimental-auto` in native metadata and exported comments.
