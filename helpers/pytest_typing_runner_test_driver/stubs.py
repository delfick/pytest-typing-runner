import dataclasses
from collections.abc import Sequence
from typing import TYPE_CHECKING, Generic, cast

from pytest_typing_runner import protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubRunResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubNoticeChecker(Generic[protocols.T_Scenario]):
    result: protocols.RunResult
    runner: protocols.ProgramRunner[protocols.T_Scenario]
    run_options: protocols.RunOptions[protocols.T_Scenario]

    def check(self, expected_notices: protocols.ProgramNotices, /) -> None:
        pass


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubProgramRunner(Generic[protocols.T_Scenario]):
    options: protocols.RunOptions[protocols.T_Scenario]

    def run(self) -> protocols.NoticeChecker[protocols.T_Scenario]:
        return StubNoticeChecker(result=StubRunResult(), run_options=self.options, runner=self)

    def short_display(self) -> str:
        return "stubrun"


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubProgramRunnerMaker(Generic[protocols.T_Scenario]):
    default_args: Sequence[str] = dataclasses.field(default_factory=list)
    do_followups: bool = True
    same_process: bool = False
    is_daemon: bool = False
    program_short: str = "stubd"

    runner_kls: type[StubProgramRunner[protocols.T_Scenario]] = StubProgramRunner

    def __call__(
        self, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.ProgramRunner[protocols.T_Scenario]:
        return self.runner_kls(options=options)


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubStrategy:
    program_short: str = "stubd"

    def program_runner_chooser(
        self, config: protocols.RunnerConfig, scenario: protocols.T_Scenario
    ) -> protocols.ProgramRunnerMaker[protocols.T_Scenario]:
        return StubProgramRunnerMaker(program_short=self.program_short)


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubRunnerConfig:
    same_process: bool = False
    typing_strategy: protocols.Strategy = dataclasses.field(default_factory=StubStrategy)


@dataclasses.dataclass(frozen=True, kw_only=True)
class StubExpectations(Generic[protocols.T_Scenario]):
    def check(self, *, notice_checker: protocols.NoticeChecker[protocols.T_Scenario]) -> None:
        pass


if TYPE_CHECKING:
    _SRR: protocols.P_RunResult = cast(StubRunResult, None)
    _SNC: protocols.P_NoticeChecker = cast(StubNoticeChecker[protocols.P_Scenario], None)
    _SR: protocols.P_ProgramRunner = cast(StubProgramRunner[protocols.P_Scenario], None)
    _SRM: protocols.P_ProgramRunnerMaker = cast(StubProgramRunnerMaker[protocols.P_Scenario], None)
    _SS: protocols.P_Strategy = cast(StubStrategy, None)
    _SM: protocols.P_StrategyMaker = StubStrategy
    _SRC: protocols.P_RunnerConfig = cast(StubRunnerConfig, None)
    _E: protocols.P_Expectations = cast(StubExpectations[protocols.P_Scenario], None)
