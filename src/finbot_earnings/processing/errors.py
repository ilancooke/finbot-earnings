"""Errors passed to a future queue adapter as retry or failed-work outcomes."""


class ContractError(ValueError):
    """Invalid or unsupported input notification."""


class WorkBusy(RuntimeError):
    """Another delivery currently owns the work."""


class StaleClaim(RuntimeError):
    """An expired or replaced worker cannot checkpoint work."""


class WorkConflict(RuntimeError):
    """The same work identity was reused with different input or configuration."""


class TechnicalFailure(RuntimeError):
    """Safe diagnostic code; transport exception text is not persisted."""

    def __init__(self, code: str, *, retryable: bool = True):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class InputReview(RuntimeError):
    """A complete filing cannot fit the provider input contract; do not retry."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
