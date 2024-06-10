import dataclasses
import pathlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunResult(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunResult.
    """

    scenario: protocols.T_Scenario
    typing_strategy: protocols.Strategy
    cwd: pathlib.Path
    runner: protocols.Runner[protocols.T_Scenario]
    args: Sequence[str]
    exit_code: int
    stdout: str
    stderr: str

    @classmethod
    def from_options(
        cls,
        options: protocols.RunOptions[protocols.T_Scenario],
        exit_code: int,
        *,
        stdout: str,
        stderr: str,
    ) -> Self:
        return cls(
            scenario=options.scenario,
            typing_strategy=options.typing_strategy,
            runner=options.runner,
            cwd=options.cwd,
            args=options.args,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )


@dataclasses.dataclass
class Expectations(Generic[protocols.T_Scenario]):
    expect_fail: bool = False

    def validate_result(self, result: protocols.RunResult[protocols.T_Scenario]) -> None:
        """
        Given the return code and output from a run of a type checker, raise an exception if it's invalid
        """
        if self.expect_fail:
            assert result.exit_code != 0
        else:
            assert result.exit_code == 0


if TYPE_CHECKING:
    _RR: protocols.RunResult[protocols.P_Scenario] = cast(RunResult[protocols.P_Scenario], None)

    _E: protocols.Expectations[protocols.P_Scenario] = cast(
        Expectations[protocols.P_Scenario], None
    )
