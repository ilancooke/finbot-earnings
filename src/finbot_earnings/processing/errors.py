"""Safe contract, concurrency and technical errors for the filing consumer."""


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
