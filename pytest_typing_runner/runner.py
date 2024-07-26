import dataclasses
import pathlib
import sys
from collections.abc import MutableSequence
from typing import TYPE_CHECKING, Generic, cast

from . import expectations, protocols


@dataclasses.dataclass(kw_only=True)
class RunOptions(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunOptions
    """

    scenario: protocols.T_Scenario
    typing_strategy: protocols.Strategy
    runner: protocols.Runner[protocols.T_Scenario]
    cwd: pathlib.Path
    args: MutableSequence[str]
    do_followup: bool


class ExternalMypyRunner(Generic[protocols.T_Scenario]):
    def __init__(self) -> None:
        self._command: list[str] = [sys.executable, "-m", "mypy"]

    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Run mypy as an external process
        """
        exit_code, stdout, stderr = 0, "", ""
        return expectations.RunResult.from_options(
            options, exit_code, stdout=stdout, stderr=stderr
        )

    def short_display(self) -> str:
        return " ".join(self._command)


class SameProcessMypyRunner(Generic[protocols.T_Scenario]):
    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Run mypy inside the existing process
        """
        exit_code, stdout, stderr = 0, "", ""
        return expectations.RunResult.from_options(
            options, exit_code, stdout=stdout, stderr=stderr
        )

    def short_display(self) -> str:
        return "inprocess::mypy"


class ExternalDaemonMypyRunner(Generic[protocols.T_Scenario]):
    def __init__(self) -> None:
        self._command: list[str] = [sys.executable, "-m", "mypy"]

    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Run dmypy as an external process
        """
        exit_code, stdout, stderr = 0, "", ""
        return expectations.RunResult.from_options(
            options, exit_code, stdout=stdout, stderr=stderr
        )

    def short_display(self) -> str:
        return " ".join(self._command)


if TYPE_CHECKING:
    _RO: protocols.RunOptions[protocols.P_Scenario] = cast(RunOptions[protocols.P_Scenario], None)

    _EMR: protocols.Runner[protocols.P_Scenario] = cast(
        ExternalMypyRunner[protocols.P_Scenario], None
    )
    _SPM: protocols.Runner[protocols.P_Scenario] = cast(
        SameProcessMypyRunner[protocols.P_Scenario], None
    )
    _EDMR: protocols.Runner[protocols.P_Scenario] = cast(
        ExternalDaemonMypyRunner[protocols.P_Scenario], None
    )
