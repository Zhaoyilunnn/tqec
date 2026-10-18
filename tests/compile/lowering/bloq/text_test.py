import pytest

from tqec.compile.lowering.base import UnsupportedLoweringError
from tqec.compile.lowering.bloq.text import coordinate, identifier, operation, template, token


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
