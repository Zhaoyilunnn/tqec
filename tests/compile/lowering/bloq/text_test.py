from typing import cast

import pytest

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq import emitter
from tqec.compile.lowering.bloq.text import coordinate, identifier, operation, template, token
from tqec.compile.tree.tree import LayerTree
from tqec.utils.exceptions import TQECError


def minimal_program() -> str:
    body = [operation("R", [(0, 0)]), "TICK", operation("M", [(0, 0)], [0])]
    return (
        "BLOQIR 1\n"
        + template(0, body)
        + "\ngraph {\n  n0 quantum {\n    instance i0 t0 @ (0,0)\n  }\n}\n"
    )


def test_real_bloq_roundtrip() -> None:
    bloq = pytest.importorskip("bloq")
    program = bloq.Bloq.from_text(minimal_program())
    program.validate()
    binary = program.to_binary()
    assert bloq.Bloq.from_text(program.to_text()).to_binary() == binary
    assert bloq.Bloq.from_binary(binary).to_text() == program.to_text()


@pytest.mark.parametrize("q", ((2**31, 0), (-(2**31) - 1, 0), (0.5, 0), (True, 0)))
def test_coordinate_range(q) -> None:
    with pytest.raises(ValueError):
        coordinate(q)


def test_text_validation() -> None:
    assert coordinate((-2, 3)) == "(-2,3)"
    assert token("a b/~") == "a%20b%2F%7E"
    assert token("") == "~"
    with pytest.raises(ValueError):
        identifier("m", -1)
    with pytest.raises(ValueError):
        operation("M", [(0, 0), (1, 1)], [0, 0])
    with pytest.raises(ValueError):
        operation("CX", [(0, 0)])
    with pytest.raises(UnsupportedLoweringError):
        operation("UNKNOWN", [(0, 0)])


def test_loader_rejects_different_codec_version(monkeypatch) -> None:
    pytest.importorskip("bloq")

    monkeypatch.setattr(emitter, "emit_bloq_text", lambda *_args, **_kwargs: minimal_program())
    monkeypatch.setattr(emitter, "version", lambda _distribution: "0.1.2")
    with pytest.raises(TQECError, match=r"found 0\.1\.2"):
        emitter.lower_to_bloq(cast(LayerTree, None), 1)


def test_signed_detector_roundtrip() -> None:
    bloq = pytest.importorskip("bloq")
    body = ["RY (0,0)", "TICK", "H (0,0)", "TICK", "MY (0,0):m0"]
    text = (
        "BLOQIR 1\n"
        + template(0, body, ["detector -m0 @ (0,0)"])
        + "\ngraph {\n  n0 quantum {\n    instance i0 t0 @ (0,0)\n  }\n}\n"
    )
    program = bloq.Bloq.from_text(text)
    program.validate()
    assert "detector -m0" in program.to_text()
    assert bloq.Bloq.from_binary(program.to_binary()).to_text() == program.to_text()
    assert not bloq.emit_stim(program).compile_detector_sampler().sample(32).any()
