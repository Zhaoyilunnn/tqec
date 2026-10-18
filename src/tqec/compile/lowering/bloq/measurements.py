"""Measurement ownership after spatial deduplication and template placement."""

from tqec.compile.lowering.bloq.text import identifier


def indices(parity: int):
    """Enumerate the records in an XOR parity deterministically."""
    while parity:
        bit = parity & -parity
        yield bit.bit_length() - 1
        parity ^= bit


class MeasurementRegistry:
    def __init__(self) -> None:
        """Allocate global addresses while keeping template-local ids distinct."""
        self.outputs: list[tuple[int, int, tuple[int, int], int]] = []
        self.by_instance: list[dict] = []
        self.offsets: list[int] = []

    def add_instance(self, instance: int, records: dict) -> None:
        """Register one instance's already deduplicated measurement outputs."""
        if instance != len(self.by_instance):
            raise ValueError("Instances must have unique, consecutive identities.")
        self.offsets.append(len(self.outputs))
        ordered = sorted((m, q, t) for q, values in records.items() for t, m, _ in values)
        if [m for m, _, _ in ordered] != list(range(len(ordered))):
            raise ValueError("Local measurement identities must be unique and consecutive.")
        self.by_instance.append(records)
        self.outputs.extend((instance, m, q, t) for m, q, t in ordered)

    def parity(self, mask: int, *, local_instance: int | None = None) -> str:
        """Render defined records, rejecting cross-instance use as a local parity."""
        terms = []
        for record in indices(mask):
            if record >= len(self.outputs):
                raise ValueError(f"Undefined measurement {record}.")
            instance, local, _, _ = self.outputs[record]
            if local_instance is not None and instance != local_instance:
                raise ValueError("A template parity cannot reference another instance.")
            term = identifier("m", local)
            terms.append(term if local_instance is not None else f"i{instance}:{term}")
        return "*".join(terms) if terms else "_"
