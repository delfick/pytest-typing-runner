from __future__ import annotations

import enum
import pathlib
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


class ScenarioHook(Protocol[T_CO_Scenario]):
    """
    The protocol for the object that is created for every test that creates a scenario.

    A default implementation is provided by ``pytest_typing_runner.ScenarioHook``

    The ``typing_scenario_hook_maker`` can be used to change which ``ScenarioHook`` is
    used for a particular pytest scope. The return of this must satisfy the ``ScenarioHookMaker``
    protocol, which the default implementation of ``ScenarioHook`` already does.
    """

    @property
    def config(self) -> RunnerConfig:
        """
        Plugin level configuration
        """

    @property
    def root_dir(self) -> pathlib.Path:
        """
        The root path the test takes place in
        """

    @property
    def scenario(self) -> T_CO_Scenario:
        """
        The scenario object under test.
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


class ScenarioRuns(Protocol):
    """
    Represents information to return in a pytest report at the end of the test

    A default implementation is provided by ``pytest_typing_runner.ScenarioRuns``
    """

    def __str__(self) -> str: ...

    def __bool__(self) -> bool: ...


class Scenario(Protocol):
    """
    Used to facilitate running and testing a type checker run

    A default implementation is provided by ``pytest_typing_runner.Scenario``

    The ``typing_scenario_kls`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.

    The ``typing_scenario_maker`` fixture will return the value from ``typing_scenario_kls``
    by default, but can be overridden if the custom class doesn't match the
    ``ScenarioMaker`` protocol.
    """

    runs: ScenarioRuns
    config: RunnerConfig
    root_dir: pathlib.Path
    scenario_hook: ScenarioHook[Self]


class ScenarioMaker(Protocol[T_Scenario]):
    """
    Represents an object that creates Scenario objects

    The default implementation of ``Scenario`` already satisfies this protocol.
    """

    def __call__(
        self,
        *,
        config: RunnerConfig,
        root_dir: pathlib.Path,
        scenario_hook: ScenarioHook[T_Scenario],
    ) -> T_Scenario: ...


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


if TYPE_CHECKING:
    P_Scenario = Scenario
    P_RunnerConfig = RunnerConfig
    P_ScenarioHook = ScenarioHook[P_Scenario]
    P_ScenarioRuns = ScenarioRuns
    P_ScenarioMaker = ScenarioMaker[P_Scenario]
    P_ScenarioHookMaker = ScenarioHookMaker[P_Scenario]
