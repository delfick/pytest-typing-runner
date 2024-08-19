import pathlib
import textwrap
from collections.abc import Iterator

import pytest
from _pytest.config.argparsing import Parser

from . import protocols
from .scenario import RunnerConfig, Scenario, ScenarioRunner


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
def typing_scenario_maker() -> protocols.ScenarioMaker[protocols.Scenario]:
    return Scenario.create


@pytest.fixture
def typing_scenario_runner_maker(
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
) -> protocols.ScenarioRunnerMaker[protocols.T_Scenario]:
    return ScenarioRunner


@pytest.fixture
def typing_scenario_runner(
    typing_runner_config: RunnerConfig,
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
    typing_scenario_runner_maker: protocols.ScenarioRunnerMaker[protocols.T_Scenario],
    request: pytest.FixtureRequest,
    tmp_path: pathlib.Path,
) -> Iterator[protocols.ScenarioRunner[protocols.T_Scenario]]:
    """
    Pytest fixture used to get a typing scenario helper and manage cleanup
    """
    runner = typing_scenario_runner_maker(
        config=typing_runner_config, root_dir=tmp_path, scenario_maker=typing_scenario_maker
    )
    request.node.user_properties.append(("typing_runner", runner))

    runner.prepare_scenario()
    try:
        yield runner
    finally:
        runner.cleanup_scenario()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    For failed tests, we add information to the pytest report from any Scenario objects
    that were added to the pytest report
    """
    if report.when == "call" and report.outcome == "failed":
        for name, val in report.user_properties:
            if isinstance(val, ScenarioRunner):
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
