from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Iterator, MutableSequence, Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import protocols


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

    def prepare_scenario(self) -> None:
        """
        Called when the scenario has been created. This method may do any mutations it
        wants on self.scenario
        """

    def cleanup_scenario(self) -> None:
        """
        Called after the test is complete. This method may do anything it wants for cleanup
        """

    @property
    def runs(self) -> protocols.ScenarioRuns[protocols.T_Scenario]:
        return self._runs

    def create_scenario_runs(self) -> protocols.ScenarioRuns[protocols.T_Scenario]:
        """
        Used to create the object that will represent information about the type checker runs
        """
        return ScenarioRuns(scenario=self._scenario)

    def add_to_pytest_report(self, name: str, sections: list[tuple[str, str]]) -> None:
        """
        Default implementation adds a section with the provided name if there were runs to report
        """
        if self.runs.has_runs:
            sections.append((name, "\n".join(self.runs.for_report())))


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
        raise NotImplementedError()

    def run_and_check_static_type_checking(
        self, expectations: protocols.Expectations[protocols.T_Scenario]
    ) -> None:
        raise NotImplementedError()


if TYPE_CHECKING:
    C_Scenario = Scenario
    C_RunnerConfig = RunnerConfig
    C_ScenarioRun = ScenarioRun[C_Scenario]
    C_ScenarioRuns = ScenarioRuns[C_Scenario]
    C_ScenarioHook = ScenarioHook[C_Scenario]
    C_ScenarioRunner = ScenarioRunner[C_Scenario]

    _RC: protocols.P_RunnerConfig = cast(C_RunnerConfig, None)

    _CS: protocols.P_Scenario = cast(C_Scenario, None)
    _CR: protocols.ScenarioRun[C_Scenario] = cast(C_ScenarioRun, None)
    _CSR: protocols.ScenarioRuns[C_Scenario] = cast(C_ScenarioRuns, None)
    _CSH: protocols.ScenarioHook[C_Scenario] = cast(C_ScenarioHook, None)
    _CSM: protocols.ScenarioMaker[C_Scenario] = C_Scenario.create
    _CSHM: protocols.ScenarioHookMaker[C_Scenario] = C_ScenarioHook
    _CSRU: protocols.ScenarioRunner[C_Scenario] = cast(C_ScenarioRunner, None)
    _CSRM: protocols.ScenarioRunnerMaker[C_Scenario] = C_ScenarioRunner
