import dataclasses
import pathlib
import sys
from collections.abc import MutableMapping, MutableSequence, Sequence
from typing import TYPE_CHECKING, Generic, cast

from . import expectations, protocols


@dataclasses.dataclass(kw_only=True)
class RunOptions(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunOptions
    """

    scenario: protocols.T_Scenario
    typing_strategy: protocols.Strategy
    runner: protocols.ProgramRunner[protocols.T_Scenario]
    cwd: pathlib.Path
    args: MutableSequence[str]
    check_paths: MutableSequence[str]
    do_followup: bool
    environment_overrides: MutableMapping[str, str | None]


class ExternalMypyRunner(Generic[protocols.T_Scenario]):
    def __init__(self, *, mypy_name: str = "mypy") -> None:
        self._command: Sequence[str] = (sys.executable, "-m", mypy_name)

    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> expectations.RunResult[protocols.T_Scenario]:
        """
        Run mypy as an external process
        """
        return expectations.RunResult.from_options(options, 0, stdout="", stderr="")

    def check_notices(
        self,
        *,
        result: protocols.RunResult[protocols.T_Scenario],
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        # TODO Implement
        return

    def short_display(self) -> str:
        return " ".join(self._command)


class SameProcessMypyRunner(Generic[protocols.T_Scenario]):
    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Run mypy inside the existing process
        """
        # TODO: implement
        return expectations.RunResult.from_options(options, 0, stdout="", stderr="")

    def check_notices(
        self,
        *,
        result: protocols.RunResult[protocols.T_Scenario],
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        # TODO: implement
        return

    def short_display(self) -> str:
        return "inprocess::mypy"


class ExternalDaemonMypyRunner(ExternalMypyRunner[protocols.T_Scenario]):
    def __init__(self) -> None:
        super().__init__(mypy_name="mypy.dmypy")


if TYPE_CHECKING:
    _RO: protocols.RunOptions[protocols.P_Scenario] = cast(RunOptions[protocols.P_Scenario], None)

    _EMR: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        ExternalMypyRunner[protocols.P_Scenario], None
    )
    _SPM: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        SameProcessMypyRunner[protocols.P_Scenario], None
    )
    _EDMR: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        ExternalDaemonMypyRunner[protocols.P_Scenario], None
    )
