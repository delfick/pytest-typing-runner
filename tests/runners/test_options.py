import dataclasses
import pathlib

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import protocols, runners, scenarios


class TestRunOptions:
    @pytest.fixture
    def runner(self, tmp_path: pathlib.Path) -> scenarios.ScenarioRunner[protocols.Scenario]:
        config = stubs.StubRunnerConfig()

        return scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )

    def test_it_has_attributes_and_can_be_cloned(
        self, runner: protocols.ScenarioRunner[protocols.Scenario], tmp_path: pathlib.Path
    ) -> None:
        program_runner_maker = stubs.StubProgramRunnerMaker[protocols.Scenario]()
        options = runners.RunOptions(
            scenario_runner=runner,
            program_runner_maker=program_runner_maker,
            cwd=runner.scenario.root_dir,
            args=["one"],
            check_paths=["two"],
            do_followup=False,
            environment_overrides={"three": "four"},
        )

        assert options.scenario_runner is runner
        assert options.program_runner_maker is program_runner_maker
        assert options.cwd == runner.scenario.root_dir
        assert options.args == ["one"]
        assert options.check_paths == ["two"]
        assert not options.do_followup
        assert options.environment_overrides == {"three": "four"}

        clone = options.clone(args=["two"])
        assert options.args == ["one"]
        assert clone.args == ["two"]

        options = clone
        assert options.scenario_runner is runner
        assert options.program_runner_maker is program_runner_maker
        assert options.cwd == runner.scenario.root_dir
        assert options.args == ["two"]
        assert options.check_paths == ["two"]
        assert not options.do_followup
        assert options.environment_overrides == {"three": "four"}

        program_runner_maker2 = stubs.StubProgramRunnerMaker[protocols.Scenario]()
        options = options.clone(
            program_runner_maker=program_runner_maker2,
            cwd=tmp_path / "two",
            args=["1"],
            check_paths=["2"],
            do_followup=True,
            environment_overrides={"5": None},
        )
        assert options.scenario_runner is runner
        assert options.program_runner_maker is program_runner_maker2
        assert options.cwd == tmp_path / "two"
        assert options.cwd != runner.scenario.root_dir
        assert options.args == ["1"]
        assert options.check_paths == ["2"]
        assert options.do_followup
        assert options.environment_overrides == {"5": None}

    def test_it_has_helpful_create_with_good_defaults(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner)

        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.cwd == runner.scenario.root_dir
        assert options.args == []
        assert options.check_paths == ["."]
        assert options.do_followup
        assert options.environment_overrides == {}

    def test_it_can_be_given_further_modifications(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        def modify1(
            options: protocols.RunOptions[protocols.Scenario],
        ) -> protocols.RunOptions[protocols.Scenario]:
            assert options.args == []
            return options.clone(args=["one"])

        def modify2(
            options: protocols.RunOptions[protocols.Scenario],
        ) -> protocols.RunOptions[protocols.Scenario]:
            assert options.args == ["one"]
            return options.clone(args=["one", "two"])

        def modify3(
            options: protocols.RunOptions[protocols.Scenario],
        ) -> protocols.RunOptions[protocols.Scenario]:
            assert options.args == ["one", "two"]
            return options.clone(check_paths=["blah"])

        options = runners.RunOptions.create(runner, modify_options=(modify1, modify2, modify3))

        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.cwd == runner.scenario.root_dir
        assert options.args == ["one", "two"]
        assert options.check_paths == ["blah"]
        assert options.do_followup
        assert options.environment_overrides == {}

    def test_it_gets_args_and_do_followup_from_program_runner(
        self, tmp_path: pathlib.Path
    ) -> None:
        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Strategy(stubs.StubStrategy):
            program_short: str = "stubd"

            def program_runner_chooser(
                self, config: protocols.RunnerConfig, scenario: protocols.T_Scenario
            ) -> protocols.ProgramRunnerMaker[protocols.T_Scenario]:
                return stubs.StubProgramRunnerMaker(
                    default_args=["stuff"], do_followups=False, program_short=self.program_short
                )

        config = stubs.StubRunnerConfig(typing_strategy=Strategy())

        runner = scenarios.ScenarioRunner[protocols.Scenario].create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )

        options = runners.RunOptions.create(runner)
        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.args == ["stuff"]
        assert not options.do_followup

        program_runner_maker = stubs.StubProgramRunnerMaker[protocols.Scenario](
            default_args=["blah"], do_followups=True
        )
        options = runners.RunOptions.create(runner, program_runner_maker=program_runner_maker)
        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.args == ["blah"]
        assert options.do_followup

        options = runners.RunOptions.create(
            runner, program_runner_maker=program_runner_maker, do_followup=False
        )
        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.args == ["blah"]
        assert not options.do_followup

        options = runners.RunOptions.create(
            runner, program_runner_maker=program_runner_maker, args=["other"]
        )
        assert options.scenario_runner is runner
        assert isinstance(options.program_runner_maker, stubs.StubProgramRunnerMaker)
        assert options.args == ["other"]
        assert options.do_followup
