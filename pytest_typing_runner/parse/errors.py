import dataclasses

from .. import errors


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidLine(errors.PyTestTypingRunnerException):
    """
    Base exception for problems with parsing lines
    """


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidInstruction(InvalidLine):
    """
    Raised when a line that looks like an invalid instruction comment is found
    """

    reason: str
    line: str

    def __str__(self) -> str:
        return f"{self.reason}: {self.line}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class TooManyModifyLines(InvalidLine):
    """
    Raised when multiple ``modify_lines`` are produced for a single line
    """

    line: str

    def __str__(self) -> str:
        return f"Can only modify a line once for all collected comments: line='{self.line}'"


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidMypyOutputLine(InvalidLine):
    """
    Raised when an invalid line from mypy output is encountered
    """

    line: str

    def __str__(self) -> str:
        return f"Line from mypy output is invalid: {self.line}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class UnknownSeverity(InvalidMypyOutputLine):
    """
    Raised when a severity is encountered that is unknown
    """

    severity: str

    def __str__(self) -> str:
        return f"Unknown severity: {self.severity}"
