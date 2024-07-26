import pathlib
import textwrap
from collections.abc import Iterator

import pytest
from _pytest.config.argparsing import Parser

from . import protocols
from .scenario import RunnerConfig, Scenario, ScenarioHook, ScenarioRunner


@pytest.fixture
def typing_runner_config(pytestconfig: pytest.Config) -> protocols.RunnerConfig:
    """
    Fixture to get a RunnerConfig with all the relevant settings from the pytest config
    """
    return RunnerConfig(
        same_process=pytestconfig.option.typing_same_process,
        typing_strategy=protocols.Strategy(pytestconfig.option.typing_strategy),
    )


@pytest.fixture
def typing_scenario_kls() -> type[Scenario]:
    return Scenario


@pytest.fixture
def typing_scenario_maker(
    typing_scenario_kls: type[protocols.T_Scenario],
) -> protocols.ScenarioMaker[protocols.T_Scenario]:
    return typing_scenario_kls.create


@pytest.fixture
def typing_scenario_hook_maker() -> protocols.ScenarioHookMaker[Scenario]:
    return ScenarioHook


@pytest.fixture
def typing_scenario_runner_maker() -> protocols.ScenarioRunnerMaker[Scenario]:
    return ScenarioRunner


@pytest.fixture
def typing_runner_scenario(
    typing_runner_config: RunnerConfig,
    typing_scenario_kls: type[protocols.T_Scenario],
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
    typing_scenario_hook_maker: protocols.ScenarioHookMaker[protocols.T_Scenario],
    typing_scenario_runner_maker: protocols.ScenarioRunnerMaker[protocols.T_Scenario],
    request: pytest.FixtureRequest,
    tmp_path: pathlib.Path,
) -> Iterator[protocols.ScenarioRunner[protocols.T_Scenario]]:
    """
    Pytest fixture used to get a typing scenario helper and manage cleanup
    """
    hook = typing_scenario_hook_maker(
        config=typing_runner_config, root_dir=tmp_path, Scenario=typing_scenario_maker
    )
    request.node.user_properties.append(("typing_runner", hook))

    hook.prepare_scenario()
    try:
        yield typing_scenario_runner_maker(scenario=hook.scenario, scenario_hook=hook)
    finally:
        hook.cleanup_scenario()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    For failed tests, we add information to the pytest report from any Scenario objects
    that were added to the pytest report
    """
    if report.when == "call" and report.outcome == "failed":
        for name, val in report.user_properties:
            if isinstance(val, ScenarioHook):
                val.add_to_pytest_report(name, report.sections)


def pytest_addoption(parser: Parser) -> None:
    """
    Define relevant options for the plugin
    """
    group = parser.getgroup("typing-runner")
    group.addoption(
        "--typing-same-process",
        action="store_true",
        help="Run in the same process. Useful for debugging, will create problems with import cache",
    )
    group.addoption(
        "--typing-strategy",
        choices=[strat.name for strat in protocols.Strategy],
        help=textwrap.dedent(protocols.Strategy.__doc__ or ""),
        default=protocols.Strategy.MYPY_INCREMENTAL.value,
    )
