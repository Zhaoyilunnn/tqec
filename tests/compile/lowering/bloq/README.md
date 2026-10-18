# Bloq lowering validation

The reference TQEC commit is `c89ff48a07d61aeae7373faa431a5fb178d9d8e3`.
Tests use Python 3.11.16, Stim 1.16.0, tqecd 0.2.1, and **bloq-py 0.1.1**
(the Python import is `bloq`). The Linux abi3 wheel SHA-256 is
`a77b5973d2cc72f606bf0500ed05f1f42587bf028821614f76432f0509025889`.
Bloq development source was inspected at `efe9d719cc45cde75da3817ce584e8e17d20b13e`;
its unreleased additions are not the text compatibility contract.

The existing `tests/compile/decoupling_baseline_test.py` is the independent Stim
reference: 42 cases spanning X and Z memory, spatial and temporal pipes, CNOT,
three-arm junctions and temporal Hadamard at scales one and two under fixed bulk,
diagonal fixed bulk and fixed boundary. It checks exact text fingerprints,
qubit, tick, measurement, detector and observable counts, and noiseless
measurement parity. These snapshots must not be regenerated for this backend.

`text_test.py` exercises the real Bloq parser, validation, and both text and
binary round trips. Install `bloq-py==0.1.1` to run the integration tests; pure
text emission must remain usable without that installation.

Custom translators, custom plaquette compilers and raw circuit layers are not
recoverable from construction specifications. Bloq lowering must reject them.
The existing diagonal spatial-H expected failures remain unsupported. A physical
operation test alone does not establish detector, flow or logical correctness.
