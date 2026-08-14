"""Framework-independent domain errors translated by the API boundary."""


class MaderaFlowNotFoundError(Exception):
    """Base error for records unavailable within caller context."""


class UnknownCallerError(MaderaFlowNotFoundError):
    """Raised when a caller ID or approved alias cannot be resolved."""

    def __init__(self, caller_id: str) -> None:
        super().__init__(f"Unknown caller '{caller_id}'.")


class UnknownLotError(MaderaFlowNotFoundError):
    """Raised when a lot ID or approved alias cannot be resolved."""

    def __init__(self, lot_id: str) -> None:
        super().__init__(f"Unknown lot '{lot_id}'.")


class LotAssignmentError(MaderaFlowNotFoundError):
    """Raised when a lot is outside the recognized caller's assignments."""

    def __init__(self) -> None:
        super().__init__("The requested lot is not assigned to this caller.")
