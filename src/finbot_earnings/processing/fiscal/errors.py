"""Safe, structured boundary outcomes; never retain exception messages."""


class ExtractionProblem(Exception):
    def __init__(self, outcome, reasons, *, retryable=False):
        self.outcome, self.reasons, self.retryable = outcome, reasons, retryable
        super().__init__(reasons[0]["code"])


def problem(code, stage, *, outcome="processing_failed", retryable=False, **details):
    return ExtractionProblem(outcome, [dict(code=code, stage=stage, **details)], retryable=retryable)
