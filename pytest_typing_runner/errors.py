import dataclasses


@dataclasses.dataclass(kw_only=True)
class PyTestTypingRunnerException(Exception):
    """
    Parent exception for all exceptions from this library
    """
