import pathlib
from collections.abc import Iterator

import pytest
from _pytest.config.argparsing import Parser

from . import protocols, scenarios, strategies


@pytest.fixture
def typing_runner_config(pytestconfig: pytest.Config) -> protocols.RunnerConfig:
    """
    Fixture to get a RunnerConfig with all the relevant settings from the pytest config
    """
    return scenarios.RunnerConfig(
        same_process=pytestconfig.option.typing_same_process,
        typing_strategy=pytestconfig.option.typing_strategy,
    )


@pytest.fixture
def typing_scenario_maker() -> protocols.ScenarioMaker[protocols.Scenario]:
    return scenarios.Scenario.create


@pytest.fixture
def typing_scenario_runner_maker(
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
) -> protocols.ScenarioRunnerMaker[protocols.T_Scenario]:
    return scenarios.ScenarioRunner.create


@pytest.fixture
def typing_scenario_runs_maker(
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
) -> protocols.ScenarioRunsMaker[protocols.T_Scenario]:
    return scenarios.ScenarioRuns.create


@pytest.fixture
def typing_scenario_root_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "scenario_root"


@pytest.fixture
def typing_scenario_runner(
    typing_runner_config: protocols.RunnerConfig,
    typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
    typing_scenario_runs_maker: protocols.ScenarioRunsMaker[protocols.T_Scenario],
    typing_scenario_runner_maker: protocols.ScenarioRunnerMaker[protocols.T_Scenario],
    typing_scenario_root_dir: pathlib.Path,
    request: pytest.FixtureRequest,
) -> Iterator[protocols.ScenarioRunner[protocols.T_Scenario]]:
    """
    Pytest fixture used to get a typing scenario helper and manage cleanup
    """
    runner = typing_scenario_runner_maker(
        config=typing_runner_config,
        root_dir=typing_scenario_root_dir,
        scenario_maker=typing_scenario_maker,
        scenario_runs_maker=typing_scenario_runs_maker,
    )
    request.node.user_properties.append(("typing_runner", runner))

    runner.cleaners.add("scenario_runner::cleanup_scenario", runner.cleanup_scenario)
    try:
        runner.prepare_scenario()
        yield runner
    finally:
        failures: list[Exception] = []
        for cleaner in runner.cleaners:
            try:
                cleaner()
            except Exception as exc:
                failures.append(exc)

        assert len(failures) == 0, failures


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    For failed tests, we add information to the pytest report from any Scenario objects
    that were added to the pytest report
    """
    if report.when == "call" and report.outcome == "failed":
        for name, val in report.user_properties:
            if callable(add_to_pytest_report := getattr(val, "add_to_pytest_report", None)):
                add_to_pytest_report(name, report.sections)


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
    info = strategies.StrategyRegistry.discover().cli_option_info()
    group.addoption(
        "--typing-strategy", help=info.help_text, type=info.str_to_strategy, default=info.default
    )
