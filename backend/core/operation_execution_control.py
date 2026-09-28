from __future__ import annotations


class OperationExecutionControlError(RuntimeError):
    """Base class for Operations execution-control signals."""


class OperationCancellationRequested(
    OperationExecutionControlError
):
    """The owning Operations request has been cancelled."""


class OperationLeaseLost(
    OperationExecutionControlError
):
    """The worker no longer owns the Operations execution lease."""
