from __future__ import annotations

import enum
import pathlib
from collections.abc import Iterator, MutableSequence, Sequence
from typing import TYPE_CHECKING, Protocol, TypeVar

from typing_extensions import Self

T_Scenario = TypeVar("T_Scenario", bound="Scenario")
T_CO_Scenario = TypeVar("T_CO_Scenario", bound="Scenario", covariant=True)


class Strategy(enum.Enum):
    """
    The caching strategy used by the plugin

    MYPY_NO_INCREMENTAL
      - mypy is run only once for each run with --no-incremental

    MYPY_INCREMENTAL
      - mypy is run twice for each run with --incremental.
      - First with an empty cache relative to the temporary directory
      - and again after that cache is made.

    MYPY_DAEMON
      - A new dmypy is started and run twice for each run
    """

    MYPY_NO_INCREMENTAL = "MYPY_NO_INCREMENTAL"
    MYPY_INCREMENTAL = "MYPY_INCREMENTAL"
    MYPY_DAEMON = "MYPY_DAEMON"


class RunOptions(Protocol[T_Scenario]):
    """
    Used to represent the options used to run a type checker. This is a mutable object
    so that the sceneario hooks may modify it before it is used
    """

    scenario: T_Scenario
    typing_strategy: Strategy
    cwd: pathlib.Path
    runner: Runner[T_Scenario]
    args: MutableSequence[str]
    do_followup: bool


class RunResult(Protocol[T_Scenario]):
    """
    Used to represent the options used to run a type checker and the result from doing so
    """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario that is being tested
        """

    @property
    def typing_strategy(self) -> Strategy:
        """
        The cache strategy this was run with
        """

    @property
    def cwd(self) -> pathlib.Path:
        """
        The path the command was run inside
        """

    @property
    def runner(self) -> Runner[T_Scenario]:
        """
        The object used to run the type checker
        """

    @property
    def args(self) -> Sequence[str]:
        """
        The list of arguments provided to the type checker
        """

    @property
    def exit_code(self) -> int:
        """
        The exit code from running the type checker
        """

    @property
    def stdout(self) -> str:
        """
        The stdout from running the type checker
        """

    @property
    def stderr(self) -> str:
        """
        The stderr from running the type checker
        """


class RunnerConfig(Protocol):
    """
    An object to represent all the options relevant to this pytest plugin

    A default implementation is provided by ``pytest_typing_runner.RunnerConfig``
    """

    @property
    def same_process(self) -> bool:
        """
        Set by the --same-process option.

        Used to know if the type checker should be run in the same process or not.
        """

    @property
    def typing_strategy(self) -> Strategy:
        """
        Set by the --typing-strategy option.

        Used to know what type checker should be used and how.
        """


class Runner(Protocol[T_Scenario]):
    """
    Used to run the static type checker
    """

    def run(self, options: RunOptions[T_Scenario]) -> RunResult[T_Scenario]:
        """
        Run the static type checker and return a result
        """

    def short_display(self) -> str:
        """
        Return a string to represent the command that was run
        """


class ScenarioHook(Protocol[T_Scenario]):
    """
    The protocol for the object that is created for every test that creates a scenario.

    A default implementation is provided by ``pytest_typing_runner.ScenarioHook``

    The ``typing_scenario_hook_maker`` can be used to change which ``ScenarioHook`` is
    used for a particular pytest scope. The return of this must satisfy the ``ScenarioHookMaker``
    protocol, which the default implementation of ``ScenarioHook`` already does.
    """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario object under test.
        """

    @property
    def runs(self) -> ScenarioRuns[T_Scenario]:
        """
        The runs of the type checker for this scenario
        """

    def prepare_scenario(self) -> None:
        """
        Called when the scenario has been created. This method may do any mutations it
        wants on self.scenario
        """

    def cleanup_scenario(self) -> None:
        """
        Called after the test is complete. This method may do anything it wants for cleanup
        """

    def determine_options(self) -> RunOptions[T_Scenario]:
        """
        Called to determine what to run the type checker with
        """

    def before_static_type_checking(self) -> None:
        """
        Ran before options are determined for doing type checking
        """

    def execute_static_checking(self, options: RunOptions[T_Scenario]) -> RunResult[T_Scenario]:
        """
        Called to use the run options to run a type checker and get a result
        """

    def add_to_pytest_report(self, name: str, sections: list[tuple[str, str]]) -> None:
        """
        Used to add a section to the pytest report
        """

    def file_modification(self, path: str, content: str | None) -> None:
        """
        Used to modify a file for the scenario and record it on scenario.runs
        """

    def check_results(
        self, result: RunResult[T_Scenario], expectations: Expectations[T_Scenario]
    ) -> None:
        """
        Called to apply the expectations to the result from running a type checker
        """


class ScenarioRun(Protocol[T_Scenario]):
    """
    Used to hold information about a single run of a type checker
    """

    @property
    def is_first(self) -> bool:
        """
        Whether this is the first run for this scenario
        """

    @property
    def is_followup(self) -> bool:
        """
        Whether this is a followup run
        """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario that was run
        """

    @property
    def file_modifications(self) -> Sequence[tuple[str, str]]:
        """
        The file modifications that were done before this run
        """

    @property
    def options(self) -> RunOptions[T_Scenario]:
        """
        The options that were used for the run
        """

    @property
    def result(self) -> RunResult[T_Scenario]:
        """
        The result from running the type checker
        """

    @property
    def expectations(self) -> Expectations[T_Scenario]:
        """
        The expectations that were used on this run
        """

    @property
    def expectation_error(self) -> Exception | None:
        """
        Any error from matching the result to the expectations for that run
        """

    def for_report(self) -> Iterator[str]:
        """
        Used to yield strings returned to present in the pytest report
        """


class ScenarioRuns(Protocol[T_Scenario]):
    """
    Represents information to return in a pytest report at the end of the test

    A default implementation is provided by ``pytest_typing_runner.ScenarioRuns``
    """

    @property
    def has_runs(self) -> bool:
        """
        Whether there were any runs to report
        """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario these runs belong to
        """

    def for_report(self) -> Iterator[str]:
        """
        Used to yield strings to place into the pytest report
        """

    def add_file_modification(self, path: str, action: str) -> None:
        """
        Used to record a file modification for the next run
        """

    def add_run(
        self,
        *,
        options: RunOptions[T_Scenario],
        result: RunResult[T_Scenario],
        expectations: Expectations[T_Scenario],
        expectation_error: Exception | None,
    ) -> ScenarioRun[T_Scenario]:
        """
        Used to add a single run to the record
        """


class Expectations(Protocol[T_Scenario]):
    """
    This objects knows how to tell if the output from a type checker matches expectations
    """

    def validate_result(self, result: RunResult[T_Scenario]) -> None:
        """
        Given the result of running a type checker, raise an exception if it doesn't match the expectations of the test
        """


class Scenario(Protocol):
    """
    Used to hold relevant information for running and testing a type checker run.

    This object is overridden to provide a mechanism for stringing custom data throughout
    all the other objects.

    A default implementation is provided by ``pytest_typing_runner.Scenario``

    The ``typing_scenario_kls`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.

    The ``typing_scenario_maker`` fixture will return the value from ``typing_scenario_kls``
    by default, but can be overridden if the custom class doesn't match the
    ``ScenarioMaker`` protocol.
    """

    same_process: bool
    typing_strategy: Strategy
    root_dir: pathlib.Path

    @classmethod
    def create(cls, *, config: RunnerConfig, root_dir: pathlib.Path) -> Self:
        """
        Constructor for the scenario that matches the ScenarioMaker interface
        """


class ScenarioRunner(Protocol[T_Scenario]):
    """
    Used to facilitate the running and testing of a type checker run.

    A default implementation is provided by ``pytest_typing_runner.ScenarioRunner``

    The ``typing_scenario_runner`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.
    """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario under test
        """

    @property
    def scenario_hook(self) -> ScenarioHook[T_Scenario]:
        """
        The hooks for the scenario
        """

    def file_modification(self, path: str, content: str | None) -> None:
        """
        Used to change a file on disk

        Implementations should forward this to scenario_hook.file_modification
        """

    def run_and_check_static_type_checking(self, expectations: Expectations[T_Scenario]) -> None:
        """
        Used to do a run of a type checker and check against the provided expectations

        Implementations should use the hooks on the scenario_hook object, ensure that
        a run is added to scenario.runs, and execute a followup if the run was the first
        and the options ask for a followup.
        """


class ScenarioMaker(Protocol[T_CO_Scenario]):
    """
    Represents an object that creates Scenario objects

    The ``create`` classmethod on a Scenario should implement this.
    """

    def __call__(self, *, config: RunnerConfig, root_dir: pathlib.Path) -> T_CO_Scenario: ...


class ScenarioHookMaker(Protocol[T_Scenario]):
    """
    Represents an object that creates Scenario Hook objects

    The default implementation of ``ScenarioHook`` already satisfies this protocol.
    """

    def __call__(
        self,
        *,
        config: RunnerConfig,
        root_dir: pathlib.Path,
        Scenario: ScenarioMaker[T_Scenario],
    ) -> ScenarioHook[T_Scenario]: ...


class ScenarioRunnerMaker(Protocol[T_Scenario]):
    """
    Represents an object that creates Scenario Runner objects

    The default implementation of ``ScenarioRunner`` already satisfies this protocol.
    """

    def __call__(
        self, *, scenario: T_Scenario, scenario_hook: ScenarioHook[T_Scenario]
    ) -> ScenarioRunner[T_Scenario]: ...


if TYPE_CHECKING:
    P_Scenario = Scenario

    P_RunOptions = RunOptions[P_Scenario]
    P_RunResult = RunResult[P_Scenario]
    P_RunnerConfig = RunnerConfig
    P_Runner = Runner[P_Scenario]
    P_ScenarioHook = ScenarioHook[P_Scenario]
    P_ScenarioRun = ScenarioRun[P_Scenario]
    P_ScenarioRuns = ScenarioRuns[P_Scenario]
    P_Expectations = Expectations[P_Scenario]
    P_ScenarioMaker = ScenarioMaker[P_Scenario]
    P_ScenarioHookMaker = ScenarioHookMaker[P_Scenario]
    P_ScenarioRunnerMaker = ScenarioRunnerMaker[P_Scenario]

    _SM: ScenarioMaker[Scenario] = Scenario.create
