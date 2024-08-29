import pathlib
import sys

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import protocols, runners, scenarios


@pytest.fixture
def runner(tmp_path: pathlib.Path) -> protocols.ScenarioRunner[protocols.Scenario]:
    return scenarios.ScenarioRunner[protocols.Scenario].create(
        config=stubs.StubRunnerConfig(),
        root_dir=tmp_path,
        scenario_maker=scenarios.Scenario.create,
        scenario_runs_maker=scenarios.ScenarioRuns.create,
    )


class TestExternalMypyRunner:
    def test_it_has_command_and_short_display(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.ExternalMypyRunner(options=options)
        assert mypy_runner.command == (sys.executable, "-m", "mypy")
        assert mypy_runner.short_display() == " ".join(mypy_runner.command)


class TestSameProcessMypyRunner:
    def test_it_has_short_display(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.SameProcessMypyRunner(options=options)
        assert mypy_runner.short_display() == "inprocess::mypy"


class TestExternalDaemonMypyRunner:
    def test_it_has_command_and_short_display(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)
        assert mypy_runner.command == (sys.executable, "-m", "mypy.dmypy")
        assert mypy_runner.short_display() == " ".join(mypy_runner.command)
