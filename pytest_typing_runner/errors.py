import dataclasses


@dataclasses.dataclass(frozen=True, kw_only=True)
class PyTestTypingRunnerException(Exception):
    """
    Parent exception for all exceptions from this library
    """
