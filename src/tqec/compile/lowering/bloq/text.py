"""Small, deterministic writers for the Bloq 0.1.1 text codec."""

from collections.abc import Sequence
from urllib.parse import quote

from tqec.compile.lowering.base import UnsupportedLoweringError

PINNED_BLOQ_VERSION = "0.1.1"
_SINGLE = frozenset({"R", "RX", "RY", "M", "MX", "MY", "H", "S", "S_DAG", "X", "Y", "Z"})
_DOUBLE = frozenset({"CX", "CY", "CZ"})


def token(value: str) -> str:
    """Encode a metadata token using Bloq's percent encoding."""
    return quote(value, safe="-_.").replace("~", "%7E") if value else "~"


def coordinate(qubit: tuple[int, int]) -> str:
    """Format an i32 coordinate without silently rounding or overflowing."""
    if len(qubit) != 2 or any(type(v) is not int or not -(2**31) <= v < 2**31 for v in qubit):
        raise ValueError(f"Expected an i32 coordinate, got {qubit!r}.")
    return f"({qubit[0]},{qubit[1]})"


def identifier(prefix: str, value: int) -> str:
    """Format a nonnegative u32 record or object identifier."""
    if type(value) is not int or not 0 <= value < 2**32:
        raise ValueError(f"Invalid {prefix} identifier: {value!r}.")
    return f"{prefix}{value}"


def operation(
    gate: str,
    targets: Sequence[tuple[int, int]],
    measurements: Sequence[int] = (),
) -> str:
    """Write a supported physical operation with explicit measurement identities."""
    if gate not in _SINGLE | _DOUBLE:
        raise UnsupportedLoweringError("bloq", gate, "unsupported physical operation")
    if not targets or (gate in _DOUBLE and len(targets) % 2):
        raise ValueError(f"Invalid target count for {gate}: {len(targets)}.")
    if gate.startswith("M"):
        if len(measurements) != len(targets) or len(set(measurements)) != len(measurements):
            raise ValueError("Each measurement output needs one distinct local identity.")
        operands = [f"{coordinate(q)}:{identifier('m', m)}" for q, m in zip(targets, measurements)]
    else:
        if measurements:
            raise ValueError("A non-measurement operation cannot define measurement records.")
        operands = [coordinate(q) for q in targets]
    return " ".join([gate, *operands])


def template(index: int, circuit: Sequence[str], side_tables: Sequence[str] = ()) -> str:
    """Write a circuit and its backend-owned semantic side tables."""
    lines = [f"template {identifier('t', index)} {{", "  circuit {"]
    lines.extend(f"    {line}" for line in circuit)
    lines.append("  }")
    lines.extend(f"  {line}" for line in side_tables)
    return "\n".join([*lines, "}"])
