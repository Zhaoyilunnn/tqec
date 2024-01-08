import cirq

from tqec.noise_models import BaseNoiseModel


class BeforeMeasurementFlipNoise(BaseNoiseModel):
    def __init__(self, p: float):
        super().__init__(p)

    def noisy_operation(self, operation: cirq.Operation) -> cirq.OP_TREE:
        if isinstance(operation.gate, cirq.MeasurementGate):
            return [
                [
                    cirq.bit_flip(self.prob).on(qubit).with_tags(cirq.VirtualTag())
                    for qubit in operation.qubits
                ],
                operation,
            ]
        else:
            return self.recurse_in_operation_if_CircuitOperation(operation)
