from typing import Literal, TypedDict

OperationStatus = Literal["success", "error"]


class OperationStarted(TypedDict):
    event: Literal["operation_started"]
    operation: str


class OperationFinished(TypedDict):
    event: Literal["operation_finished"]
    operation: str
    duration: float
    status: OperationStatus


ObservabilityEvent = OperationStarted | OperationFinished


def operation_started(operation: str) -> OperationStarted:
    """Create an operation-started event."""
    return {
        "event": "operation_started",
        "operation": operation,
    }


def operation_finished(
    operation: str,
    duration: float,
    status: OperationStatus,
) -> OperationFinished:
    """Create an operation-finished event."""
    return {
        "event": "operation_finished",
        "operation": operation,
        "duration": duration,
        "status": status,
    }
