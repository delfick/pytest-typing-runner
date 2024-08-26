from __future__ import annotations

import dataclasses
import pathlib
import shutil
import textwrap
from collections.abc import Iterator, MutableMapping, MutableSequence, Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import notices, protocols, runner


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunnerConfig:
    """
    Default implementation of the protocols.RunnerConfig.
    """

    same_process: bool
    typing_strategy_maker: protocols.StrategyMaker


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunCleaners:
    """
    Object that holds cleanup functions to be run at the end
    of the test
    """

    _cleaners: MutableMapping[str, protocols.RunCleaner] = dataclasses.field(
        init=False, default_factory=dict
    )

    def add(self, unique_identifier: str, cleaner: protocols.RunCleaner) -> None:
        self._cleaners[unique_identifier] = cleaner

    def __iter__(self) -> Iterator[protocols.RunCleaner]:
        yield from self._cleaners.values()


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRun(Generic[protocols.T_Scenario]):
    """
    Default implementation of the protocols.ScenarioRun
    """

    is_first: bool
    is_followup: bool
    scenario: protocols.T_Scenario
    checker: protocols.NoticeChecker[protocols.T_Scenario]
    expectations: protocols.Expectations[protocols.T_Scenario]
    expectation_error: Exception | None
    file_modifications: Sequence[tuple[str, str]]

    def for_report(self) -> Iterator[str]:
        for path, action in self.file_modifications:
            yield f"* {action:10s}: {path}"

        if self.is_followup:
            yield "> [followup run]"
        else:
            command = " ".join(
                [
                    self.checker.runner.short_display(),
                    *self.checker.runner.options.args,
                    *self.checker.runner.options.check_paths,
                ]
            )
            yield f"> {command}"

        yield f"| exit_code={self.checker.result.exit_code}"
        for line in self.checker.result.stdout.split("\n"):
            yield f"| stdout: {line}"
        for line in self.checker.result.stderr.split("\n"):
            yield f"| stderr: {line}"
        if self.expectation_error:
            yield f"!!! {self.expectation_error}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRuns(Generic[protocols.T_Scenario]):
    """
    Default implementation of the protocols.ScenarioRuns.
    """

    scenario: protocols.T_Scenario
    _runs: MutableSequence[protocols.ScenarioRun[protocols.T_Scenario]] = dataclasses.field(
        init=False, default_factory=list
    )
    _file_modifications: list[tuple[str, str]] = dataclasses.field(
        init=False, default_factory=list
    )

    def for_report(self) -> Iterator[str]:
        if not self._runs:
            return
        else:
            for i, run in enumerate(self._runs):
                yield f":: Run {i+1}"
                for line in run.for_report():
                    yield f"   | {line}"

    @property
    def has_runs(self) -> bool:
        return bool(self._runs)

    def add_file_modification(self, path: str, action: str) -> None:
        self._file_modifications.append((path, action))

    def add_run(
        self,
        *,
        checker: protocols.NoticeChecker[protocols.T_Scenario],
        expectations: protocols.Expectations[protocols.T_Scenario],
        expectation_error: Exception | None,
    ) -> protocols.ScenarioRun[protocols.T_Scenario]:
        """
        Used to add a single run to the record
        """
        file_modifications = tuple(self._file_modifications)
        self._file_modifications.clear()

        run = ScenarioRun(
            scenario=self.scenario,
            is_first=not self.has_runs,
            is_followup=checker.runner.options.do_followup and len(self._runs) == 1,
            checker=checker,
            expectations=expectations,
            expectation_error=expectation_error,
            file_modifications=file_modifications,
        )
        self._runs.append(run)
        return run


@dataclasses.dataclass
class Expects:
    failure: bool = False
    daemon_restarted: bool = False


@dataclasses.dataclass(frozen=True, kw_only=True)
class Scenario:
    """
    Default implementation of the protocols.Scenario
    """

    root_dir: pathlib.Path
    same_process: bool
    typing_strategy: protocols.Strategy

    expects: Expects = dataclasses.field(init=False, default_factory=Expects)
    check_paths: list[str] = dataclasses.field(default_factory=lambda: ["."])

    @classmethod
    def create(cls, config: protocols.RunnerConfig, root_dir: pathlib.Path) -> Self:
        return cls(
            root_dir=root_dir,
            same_process=config.same_process,
            typing_strategy=config.typing_strategy_maker(),
        )


class ScenarioRunner(Generic[protocols.T_Scenario]):
    def __init__(
        self,
        *,
        config: protocols.RunnerConfig,
        root_dir: pathlib.Path,
        scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
    ) -> None:
        self.scenario = scenario_maker(config=config, root_dir=root_dir)
        self.program_runner_maker = self.scenario.typing_strategy.program_runner_chooser(
            scenario=self.scenario
        )
        self.runs = self.create_scenario_runs()
        self.cleaners = RunCleaners()

    def create_scenario_runs(self) -> protocols.ScenarioRuns[protocols.T_Scenario]:
        """
        Used to create the object that will represent information about the type checker runs
        """
        return ScenarioRuns(scenario=self.scenario)

    def prepare_scenario(self) -> None:
        """
        Default implementation does not need to do any extra preparation
        """

    def cleanup_scenario(self) -> None:
        """
        Default implementation does not need to do any extra cleanup
        """

    def add_to_pytest_report(self, name: str, sections: list[tuple[str, str]]) -> None:
        """
        Default implementation adds a section with the provided name if there were runs to report
        """
        if self.runs.has_runs:
            sections.append((name, "\n".join(self.runs.for_report())))

    def file_modification(self, path: str, content: str | None) -> None:
        location = self.scenario.root_dir / path
        if not location.is_relative_to(self.scenario.root_dir):
            raise ValueError("Tried to modify a file outside of the test root")

        if location.exists():
            if content is None:
                action = "delete"
                shutil.rmtree(location)
            else:
                action = "change"
                new_content = textwrap.dedent(content)
                if location.read_text() == new_content:
                    return
                location.write_text(new_content)
        else:
            if content is None:
                action = "already_deleted"
            else:
                action = "create"
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_text(textwrap.dedent(content))

        self.runs.add_file_modification(path, action)

    def execute_static_checking(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.NoticeChecker[protocols.T_Scenario]:
        """
        Default implementation returns the result of running the runner on options with those options
        """
        return options.make_program_runner(options=options).run()

    def run_and_check(
        self,
        setup_expectations: protocols.ExpectationsSetup[protocols.T_Scenario],
        *,
        _options: protocols.RunOptions[protocols.T_Scenario] | None = None,
    ) -> None:
        if _options is not None:
            options = _options
        else:
            options = self.determine_options()

        make_expectations = setup_expectations(options=options)
        checker = self.execute_static_checking(options=options)
        expectations = make_expectations(notice_checker=checker)

        try:
            expectations.check()
        except Exception as err:
            self.runs.add_run(
                checker=checker,
                expectations=expectations,
                expectation_error=err,
            )
            raise
        else:
            run = self.runs.add_run(
                checker=checker,
                expectations=expectations,
                expectation_error=None,
            )

        if options.do_followup and run.is_first:
            repeat_expectations: protocols.ExpectationsSetup[protocols.T_Scenario] = (
                lambda options: lambda notice_checker: expectations
            )
            self.run_and_check(repeat_expectations, _options=options)

    def determine_options(self) -> runner.RunOptions[protocols.T_Scenario]:
        """
        Default implementation uses the plugin config to determine the bare essential options
        """
        return runner.RunOptions(
            scenario_runner=self,
            make_program_runner=self.program_runner_maker,
            cwd=self.scenario.root_dir,
            check_paths=self.scenario.check_paths,
            args=list(self.program_runner_maker.default_args),
            do_followup=self.program_runner_maker.do_followups,
            environment_overrides={},
            cleaners=self.cleaners,
        )

    def normalise_program_runner_notice(
        self,
        options: protocols.RunOptions[protocols.T_Scenario],
        notice: protocols.ProgramNotice,
        /,
    ) -> protocols.ProgramNotice:
        """
        No extra normalisation by default
        """
        return notice

    def generate_program_notices(self) -> protocols.ProgramNotices:
        return notices.ProgramNotices()


if TYPE_CHECKING:
    C_Scenario = Scenario
    C_RunnerConfig = RunnerConfig
    C_ScenarioRun = ScenarioRun[C_Scenario]
    C_ScenarioRuns = ScenarioRuns[C_Scenario]
    C_ScenarioRunner = ScenarioRunner[C_Scenario]

    _RC: protocols.P_RunnerConfig = cast(C_RunnerConfig, None)

    _CS: protocols.P_Scenario = cast(C_Scenario, None)
    _CSR: protocols.ScenarioRuns[C_Scenario] = cast(C_ScenarioRuns, None)
    _CSM: protocols.ScenarioMaker[C_Scenario] = C_Scenario.create
    _CSRU: protocols.ScenarioRunner[C_Scenario] = cast(C_ScenarioRunner, None)

    _E: protocols.Expects = cast(Expects, None)
    _RCS: protocols.RunCleaners = cast(RunCleaners, None)
