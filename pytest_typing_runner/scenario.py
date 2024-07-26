from __future__ import annotations

import dataclasses
import pathlib
import shutil
from collections.abc import Iterator, MutableSequence, Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self, assert_never

from . import protocols, runner


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunnerConfig:
    """
    Default implementation of the protocols.RunnerConfig.
    """

    same_process: bool
    typing_strategy: protocols.Strategy

    def __post_init__(self) -> None:
        if self.typing_strategy is protocols.Strategy.MYPY_DAEMON and self.same_process:
            raise ValueError(
                "The DAEMON strategy cannot also be in run in the same pytest process"
            )


class ScenarioHook(Generic[protocols.T_Scenario]):
    """
    Default implementation of the protocols.ScenarioHook
    """

    def __init__(
        self,
        *,
        config: protocols.RunnerConfig,
        root_dir: pathlib.Path,
        Scenario: protocols.ScenarioMaker[protocols.T_Scenario],
    ) -> None:
        self._scenario = Scenario(config=config, root_dir=root_dir)
        self._runs = self.create_scenario_runs()

    @property
    def scenario(self) -> protocols.T_Scenario:
        return self._scenario

    @property
    def runs(self) -> protocols.ScenarioRuns[protocols.T_Scenario]:
        return self._runs

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

    def determine_options(self) -> protocols.RunOptions[protocols.T_Scenario]:
        """
        Default implementation uses the plugin config to determine the bare essential options
        """
        cwd = self.scenario.root_dir
        run: protocols.Runner[protocols.T_Scenario]

        if self.scenario.typing_strategy is protocols.Strategy.MYPY_INCREMENTAL:
            if self.scenario.same_process:
                run = runner.SameProcessMypyRunner()
            else:
                run = runner.ExternalMypyRunner()
            args = ["--incremental"]
            do_followup = True
        elif self.scenario.typing_strategy is protocols.Strategy.MYPY_NO_INCREMENTAL:
            if self.scenario.same_process:
                run = runner.SameProcessMypyRunner()
            else:
                run = runner.ExternalMypyRunner()
            args = ["--no-incremental"]
            do_followup = False
        elif self.scenario.typing_strategy is protocols.Strategy.MYPY_DAEMON:
            run = runner.ExternalDaemonMypyRunner()
            args = ["run", "--"]
            do_followup = True
        else:
            assert_never(self.scenario.typing_strategy)

        return runner.RunOptions(
            scenario=self.scenario,
            typing_strategy=self.scenario.typing_strategy,
            runner=run,
            cwd=cwd,
            args=args,
            do_followup=do_followup,
        )

    def before_static_type_checking(self) -> None:
        """
        Default implementation has nothing to do before options are determined
        """

    def execute_static_checking(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Default implementation returns the result of running the runner on options with those options
        """
        return options.runner.run(options)

    def check_results(
        self,
        result: protocols.RunResult[protocols.T_Scenario],
        expectations: protocols.Expectations[protocols.T_Scenario],
    ) -> None:
        """
        Default implementation uses the expectations to match against the results
        """
        expectations.validate_result(result)

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
                location.write_text(content)
        else:
            if content is None:
                action = "already_deleted"
            else:
                action = "create"
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_text(content)

        self.runs.add_file_modification(path, action)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRun(Generic[protocols.T_Scenario]):
    """
    Default implementation of the protocols.ScenarioRun
    """

    is_first: bool
    is_followup: bool
    scenario: protocols.T_Scenario
    options: protocols.RunOptions[protocols.T_Scenario]
    result: protocols.RunResult[protocols.T_Scenario]
    expectations: protocols.Expectations[protocols.T_Scenario]
    expectation_error: Exception | None
    file_modifications: Sequence[tuple[str, str]]

    def for_report(self) -> Iterator[str]:
        for path, action in self.file_modifications:
            yield f" * {action:10s}: {path}"

        if self.is_followup:
            yield "> [followup run]"
        else:
            yield f"> {self.options.runner.short_display()} {' '.join(self.options.args)}"

        yield "| exit_code={self.result.exit_code}"
        for line in self.result.stdout.split("\n"):
            yield f"| stdout: {line}"
        for line in self.result.stderr.split("\n"):
            yield f"| stderr: {line}"
        if self.expectation_error:
            yield "!!! {self.expectation_error}"


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
        options: protocols.RunOptions[protocols.T_Scenario],
        result: protocols.RunResult[protocols.T_Scenario],
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
            is_followup=options.do_followup and len(self._runs) == 1,
            options=options,
            result=result,
            expectations=expectations,
            expectation_error=expectation_error,
            file_modifications=file_modifications,
        )
        self._runs.append(run)
        return run


@dataclasses.dataclass(kw_only=True)
class Scenario:
    """
    Default implementation of the protocols.Scenario
    """

    root_dir: pathlib.Path
    same_process: bool
    typing_strategy: protocols.Strategy

    @classmethod
    def create(cls, *, config: protocols.RunnerConfig, root_dir: pathlib.Path) -> Self:
        return cls(
            same_process=config.same_process,
            typing_strategy=config.typing_strategy,
            root_dir=root_dir,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRunner(Generic[protocols.T_Scenario]):
    scenario: protocols.T_Scenario
    scenario_hook: protocols.ScenarioHook[protocols.T_Scenario]

    def file_modification(self, path: str, content: str | None) -> None:
        self.scenario_hook.file_modification(path, content)

    def run_and_check_static_type_checking(
        self, expectations: protocols.Expectations[protocols.T_Scenario]
    ) -> None:
        self.scenario_hook.before_static_type_checking()
        options = self.scenario_hook.determine_options()
        result = self.scenario_hook.execute_static_checking(options)

        try:
            self.scenario_hook.check_results(result, expectations)
        except Exception as err:
            self.scenario_hook.runs.add_run(
                options=options,
                result=result,
                expectations=expectations,
                expectation_error=err,
            )
            raise
        else:
            run = self.scenario_hook.runs.add_run(
                options=options,
                result=result,
                expectations=expectations,
                expectation_error=None,
            )

        if options.do_followup and run.is_first:
            self.run_and_check_static_type_checking(expectations)


if TYPE_CHECKING:
    C_Scenario = Scenario
    C_RunnerConfig = RunnerConfig
    C_ScenarioRun = ScenarioRun[C_Scenario]
    C_ScenarioRuns = ScenarioRuns[C_Scenario]
    C_ScenarioHook = ScenarioHook[C_Scenario]
    C_ScenarioRunner = ScenarioRunner[C_Scenario]

    _RC: protocols.P_RunnerConfig = cast(C_RunnerConfig, None)

    _CS: protocols.P_Scenario = cast(C_Scenario, None)
    _CSR: protocols.ScenarioRuns[C_Scenario] = cast(C_ScenarioRuns, None)
    _CSH: protocols.ScenarioHook[C_Scenario] = cast(C_ScenarioHook, None)
    _CSM: protocols.ScenarioMaker[C_Scenario] = C_Scenario.create
    _CSHM: protocols.ScenarioHookMaker[C_Scenario] = C_ScenarioHook
    _CSRU: protocols.ScenarioRunner[C_Scenario] = cast(C_ScenarioRunner, None)
    _CSRM: protocols.ScenarioRunnerMaker[C_Scenario] = C_ScenarioRunner
