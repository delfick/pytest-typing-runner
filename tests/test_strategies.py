import argparse
import dataclasses
import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import runners, scenarios, strategies


class TestStrategyRegistry:
    def test_it_has_the_ability_to_add_remove_change_strategies(self) -> None:
        registry = strategies.StrategyRegistry()
        assert registry.choices == []
        with pytest.raises(strategies.NoStrategiesRegistered):
            registry.default
        assert registry.get_strategy(name="one") is None

        maker_one = lambda: stubs.StubStrategy()

        registry.register(
            name="one",
            description="a thing\nand stuff",
            maker=maker_one,
            make_default=True,
        )

        assert registry.choices == ["one"]
        assert registry.default == "one"
        assert registry.get_strategy(name="one") == ("a thing\nand stuff", maker_one)

        maker_two = lambda: stubs.StubStrategy()

        registry.register(
            name="two",
            description="another thing",
            maker=maker_two,
            make_default=False,
        )

        assert registry.choices == ["one", "two"]
        assert registry.default == "one"
        assert registry.get_strategy(name="two") == ("another thing", maker_two)

        cli_info = registry.cli_option_info()
        assert cli_info.str_to_maker("one") is maker_one
        assert cli_info.str_to_maker("two") is maker_two

        with pytest.raises(argparse.ArgumentTypeError) as e:
            cli_info.str_to_maker("three")

        assert str(e.value) == "Unknown strategy type: 'three', available are one, two"

        assert (
            cli_info.help_text.strip()
            == textwrap.dedent("""
            The caching strategy used by the plugin

            one
                a thing
                and stuff

            two
                another thing
            """).strip()
        )
        assert cli_info.default == "one"
        assert cli_info.choices == ["one", "two"]

        # And can delete
        registry.remove_strategy(name="two")
        assert registry.choices == ["one"]
        assert registry.default == "one"
        assert registry.get_strategy(name="two") is None

        cli_info = registry.cli_option_info()
        assert cli_info.str_to_maker("one") is maker_one

        with pytest.raises(argparse.ArgumentTypeError) as e:
            cli_info.str_to_maker("two")

        assert str(e.value) == "Unknown strategy type: 'two', available are one"

        assert (
            cli_info.help_text.strip()
            == textwrap.dedent("""
            The caching strategy used by the plugin

            one
                a thing
                and stuff
            """).strip()
        )
        assert cli_info.default == "one"
        assert cli_info.choices == ["one"]


class TestDefaultStrategies:
    def test_it_has_the_three_mypy_options(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        scenario_runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = scenario_runner.determine_options()

        registry = strategies.StrategyRegistry()
        strategies.register_default_strategies(registry)

        assert registry.choices == sorted(
            ["MYPY_NO_INCREMENTAL", "MYPY_INCREMENTAL", "MYPY_DAEMON"]
        )

        incremental_strat_maker = registry.get_strategy(name="MYPY_INCREMENTAL")
        assert incremental_strat_maker is not None
        no_incremental_strat_maker = registry.get_strategy(name="MYPY_NO_INCREMENTAL")
        assert no_incremental_strat_maker is not None
        daemon_strat_maker = registry.get_strategy(name="MYPY_DAEMON")
        assert daemon_strat_maker is not None

        incremental_strat = incremental_strat_maker[1]()
        no_incremental_strat = no_incremental_strat_maker[1]()
        daemon_strat = daemon_strat_maker[1]()

        assert incremental_strat.program_short == "mypy"
        assert no_incremental_strat.program_short == "mypy"
        assert daemon_strat.program_short == "mypy"

        scenario = scenario_runner.scenario
        incremental = incremental_strat.program_runner_chooser(scenario=scenario)
        no_incremental = no_incremental_strat.program_runner_chooser(scenario=scenario)
        daemon = daemon_strat.program_runner_chooser(scenario=scenario)

        assert incremental.default_args == ["--incremental"]
        assert no_incremental.default_args == ["--no-incremental"]
        assert daemon.default_args == ["run", "--"]

        assert incremental.do_followups
        assert not no_incremental.do_followups
        assert daemon.do_followups

        assert not incremental.is_daemon
        assert not no_incremental.is_daemon
        assert daemon.is_daemon

        assert not scenario.same_process

        incremental_maker = incremental_strat.program_runner_chooser(scenario=scenario)
        no_incremental_maker = no_incremental_strat.program_runner_chooser(scenario=scenario)
        daemon_maker = daemon_strat.program_runner_chooser(scenario=scenario)

        assert isinstance(incremental_maker(options=options), runners.ExternalMypyRunner)
        assert isinstance(no_incremental_maker(options=options), runners.ExternalMypyRunner)
        assert isinstance(daemon_maker(options=options), runners.ExternalDaemonMypyRunner)

        scenario_same_process = dataclasses.replace(scenario, same_process=True)
        options_same_process = dataclasses.replace(
            options,
            scenario_runner=dataclasses.replace(scenario_runner, scenario=scenario_same_process),
        )

        incremental_maker = incremental_strat.program_runner_chooser(
            scenario=scenario_same_process
        )
        no_incremental_maker = no_incremental_strat.program_runner_chooser(
            scenario=scenario_same_process
        )
        daemon_maker = daemon_strat.program_runner_chooser(scenario=scenario_same_process)

        assert isinstance(
            incremental_maker(options=options_same_process), runners.SameProcessMypyRunner
        )
        assert isinstance(
            no_incremental_maker(options=options_same_process), runners.SameProcessMypyRunner
        )

        with pytest.raises(ValueError) as e:
            daemon_maker(options=options_same_process)

        assert str(e.value) == "The mypy daemon cannot be run in the same process"
