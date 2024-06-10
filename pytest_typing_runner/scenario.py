from __future__ import annotations

import dataclasses
import pathlib
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
        self.config = config
        self.root_dir = root_dir
        self.scenario = Scenario(config=config, root_dir=root_dir, scenario_hook=self)

    def prepare_scenario(self) -> None:
        """
        Called when the scenario has been created. This method may do any mutations it
        wants on self.scenario
        """

    def cleanup_scenario(self) -> None:
        """
        Called after the test is complete. This method may do anything it wants for cleanup
        """


class ScenarioRuns:
    """
    Default implementation of the protocols.ScenarioRuns.
    """

    def __init__(self) -> None:
        self._runs: list[str] = []

    def __str__(self) -> str:
        if not self._runs:
            return ""
        else:
            return (
                self._runs.pop(0)
                + "\n"
                + "\n".join("" if not run else f" - {run}" for run in self._runs)
            )

    def __bool__(self) -> bool:
        return bool(self._runs)


@dataclasses.dataclass(kw_only=True)
class Scenario:
    """
    Default implementation of the protocols.Scenario
    """

    config: protocols.RunnerConfig
    root_dir: pathlib.Path
    scenario_hook: protocols.ScenarioHook[Self]
    runs: protocols.ScenarioRuns = dataclasses.field(init=False, default_factory=ScenarioRuns)


if TYPE_CHECKING:
    C_Scenario = Scenario
    C_RunnerConfig = RunnerConfig
    C_ScenarioRuns = ScenarioRuns
    C_ScenarioHook = ScenarioHook[C_Scenario]

    _RC: protocols.P_RunnerConfig = cast(C_RunnerConfig, None)
    _SR: protocols.P_ScenarioRuns = cast(C_ScenarioRuns, None)

    _CS: protocols.P_Scenario = cast(C_Scenario, None)
    _CSH: protocols.ScenarioHook[C_Scenario] = cast(C_ScenarioHook, None)
    _CSM: protocols.ScenarioMaker[C_Scenario] = C_Scenario
    _CSHM: protocols.ScenarioHookMaker[C_Scenario] = C_ScenarioHook
