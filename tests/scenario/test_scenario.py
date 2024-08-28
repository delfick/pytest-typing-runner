import dataclasses
import os
import pathlib
import textwrap
from typing import TypedDict

import pytest
from pytest_typing_runner_test_driver import stubs
from typing_extensions import NotRequired

from pytest_typing_runner import notices, protocols, scenarios


class TestScenario:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        scenario = scenarios.Scenario(root_dir=tmp_path)
        assert scenario.root_dir == tmp_path
        assert not scenario.expects.failure
        assert not scenario.expects.daemon_restarted

    def test_it_has_a_create_classmethod(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        scenario = scenarios.Scenario.create(config, tmp_path)

        # root_dir comes from create method
        assert scenario.root_dir == tmp_path

        # Rest is defaults
        assert not scenario.expects.failure
        assert not scenario.expects.daemon_restarted


class TestScenarioRunner:
    def test_it_has_attributes(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        scenario = scenarios.Scenario.create(config, tmp_path)
        program_runner_maker = stubs.StubProgramRunnerMaker[scenarios.Scenario]()
        runs = scenarios.ScenarioRuns(scenario=scenario)
        cleaners = scenarios.RunCleaners()

        runner = scenarios.ScenarioRunner(
            scenario=scenario,
            default_program_runner_maker=program_runner_maker,
            runs=runs,
            cleaners=cleaners,
        )
        assert runner.scenario is scenario
        assert runner.default_program_runner_maker is program_runner_maker
        assert runner.runs is runs
        assert runner.cleaners is cleaners

    def test_it_has_create_classmethod(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()

        runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        assert isinstance(runner.scenario, scenarios.Scenario)
        assert isinstance(runner.default_program_runner_maker, stubs.StubProgramRunnerMaker)
        assert isinstance(runner.runs, scenarios.ScenarioRuns)
        assert isinstance(runner.cleaners, scenarios.RunCleaners)

    @pytest.fixture
    def runner(self, tmp_path: pathlib.Path) -> scenarios.ScenarioRunner[protocols.Scenario]:
        config = stubs.StubRunnerConfig()

        return scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )

    def test_it_can_add_to_pytest_report(
        self, runner: scenarios.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runner.determine_options()
        notice_checker = options.make_program_runner(options=options).run()
        runner.runs.add_run(checker=notice_checker, expectation_error=None)

        options = runner.determine_options()
        notice_checker = options.make_program_runner(options=options).run()
        runner.runs.add_run(checker=notice_checker, expectation_error=None)

        name = "the report!"
        sections: list[tuple[str, str]] = []

        runner.add_to_pytest_report(name, sections)

        output = textwrap.dedent("""
        :: Run 1
           | > stubrun .
           | | exit_code=0
           | | stdout:
           | | stderr:
        :: Run 2
           | > [followup run]
           | | exit_code=0
           | | stdout:
           | | stderr:
        """).strip()

        assert sections == [(name, output)]

    def test_it_can_make_and_execute_program_runner(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []
        config = stubs.StubRunnerConfig()

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Runner(stubs.StubProgramRunner[protocols.Scenario]):
            def run(self) -> protocols.NoticeChecker[protocols.Scenario]:
                notice_checker = stubs.StubNoticeChecker(result=stubs.StubRunResult(), runner=self)
                called.append(("run", notice_checker))
                return notice_checker

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class ProgramRunnerMaker(stubs.StubProgramRunnerMaker[protocols.Scenario]):
            def __call__(
                self, *, options: protocols.RunOptions[protocols.Scenario]
            ) -> protocols.ProgramRunner[protocols.Scenario]:
                called.append(("make", options))
                return Runner(options=options)

        make_program_runner = ProgramRunnerMaker()
        scenario: protocols.Scenario = scenarios.Scenario.create(config, tmp_path)
        runner = scenarios.ScenarioRunner(
            scenario=scenario,
            default_program_runner_maker=make_program_runner,
            runs=scenarios.ScenarioRuns(scenario=scenario),
            cleaners=scenarios.RunCleaners(),
        )

        options = runner.determine_options()
        assert options.make_program_runner is make_program_runner
        assert called == []
        checker = runner.execute_static_checking(options=options)
        assert called == [("make", options), ("run", checker)]

    def test_it_can_make_run_options(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        make_program_runner = stubs.StubProgramRunnerMaker[protocols.Scenario](
            default_args=["one", "two"], do_followups=False
        )
        scenario: protocols.Scenario = scenarios.Scenario.create(config, tmp_path)
        runner = scenarios.ScenarioRunner(
            scenario=scenario,
            default_program_runner_maker=make_program_runner,
            runs=scenarios.ScenarioRuns(scenario=scenario),
            cleaners=scenarios.RunCleaners(),
        )

        options = runner.determine_options()
        assert options.scenario_runner is runner
        assert options.make_program_runner is make_program_runner
        assert options.cwd == scenario.root_dir
        assert options.check_paths == ["."]
        assert options.args == ["one", "two"]
        assert options.do_followup is False
        assert options.environment_overrides == {}

        # And make sure args is a copy
        options.args.append("three")
        assert options.args == ["one", "two", "three"]
        assert make_program_runner.default_args == ["one", "two"]

    def test_it_can_generate_program_notices(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        assert runner.generate_program_notices() == notices.ProgramNotices()

    class TestFileModification:
        def test_it_adds_to_the_runs(
            self, runner: scenarios.ScenarioRunner[protocols.Scenario]
        ) -> None:
            assert not runner.runs.has_runs

            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r1 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r1.file_modifications) == []

            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r2 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r2.file_modifications) == []

            runner.file_modification("one", "two")
            runner.file_modification("two/more", "three")
            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r3 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r3.file_modifications) == [("one", "create"), ("two/more", "create")]

            runner.file_modification("one", None)
            runner.file_modification("ghost", None)
            runner.file_modification("two/more", "four")
            runner.file_modification("five", "six")
            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r4 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r4.file_modifications) == [
                ("one", "delete"),
                ("ghost", "already_deleted"),
                ("two/more", "change"),
                ("five", "create"),
            ]

            runner.file_modification("seven", "blah")
            runner.file_modification("two", None)
            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r5 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r5.file_modifications) == [("seven", "create"), ("two", "delete")]

        def test_it_doesnt_add_no_changes(
            self, runner: scenarios.ScenarioRunner[protocols.Scenario]
        ) -> None:
            runner.file_modification("one", "two")
            runner.file_modification("two/more", "three")
            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r1 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r1.file_modifications) == [("one", "create"), ("two/more", "create")]

            runner.file_modification("one", "two")
            runner.file_modification("two/other", "four")
            options = runner.determine_options()
            notice_checker = options.make_program_runner(options=options).run()
            r3 = runner.runs.add_run(checker=notice_checker, expectation_error=None)
            assert list(r3.file_modifications) == [("two/other", "create")]

        def test_it_performs_a_textwrap(
            self, runner: protocols.ScenarioRunner[protocols.Scenario]
        ) -> None:
            content = "\n  well\n  hi\n  there"
            runner.file_modification("one", content)

            dedented = textwrap.dedent(content)
            assert content != dedented
            found = (runner.scenario.root_dir / "one").read_text()
            assert found == dedented
            assert found == "\nwell\nhi\nthere"

        def test_it_changes_the_root_dir(
            self, runner: protocols.ScenarioRunner[protocols.Scenario]
        ) -> None:
            def discover_root_dir() -> dict[str, str]:
                result: dict[str, str] = {}
                for root, _, files in os.walk(runner.scenario.root_dir):
                    for name in files:
                        location = pathlib.Path(root, name)
                        path = location.relative_to(runner.scenario.root_dir)
                        result[str(path)] = location.read_text()
                return result

            runner.file_modification("one", "two")
            runner.file_modification("two/more", "three")
            assert discover_root_dir() == {"one": "two", "two/more": "three"}

            runner.file_modification("one", None)
            runner.file_modification("ghost", None)
            runner.file_modification("two/more", "four")
            runner.file_modification("two/other", "hi")
            runner.file_modification("five", "six")
            assert discover_root_dir() == {"two/more": "four", "two/other": "hi", "five": "six"}

            runner.file_modification("seven", "blah")
            runner.file_modification("two", None)
            assert discover_root_dir() == {"seven": "blah", "five": "six"}

    class TestRunAndCheck:
        def test_it_does_options_setup_run_expectations(self, tmp_path: pathlib.Path) -> None:
            called: list[object] = []

            class Made(TypedDict):
                options: NotRequired[protocols.RunOptions[protocols.Scenario]]
                checker: NotRequired[protocols.NoticeChecker[protocols.Scenario]]
                expectations: NotRequired[protocols.Expectations[protocols.Scenario]]

            made: Made = {}

            @dataclasses.dataclass(frozen=True, kw_only=True)
            class Runner(scenarios.ScenarioRunner[protocols.Scenario]):
                def determine_options(self) -> protocols.RunOptions[protocols.Scenario]:
                    # Disable followup!
                    options = super().determine_options().clone(do_followup=False)
                    called.append(("determine_options", options))
                    made["options"] = options
                    return options

                def execute_static_checking(
                    self, options: protocols.RunOptions[protocols.Scenario]
                ) -> protocols.NoticeChecker[protocols.Scenario]:
                    checker = stubs.StubNoticeChecker(
                        result=stubs.StubRunResult(exit_code=1, stdout="one\ntwo"),
                        runner=stubs.StubProgramRunner(options=options),
                    )
                    called.append(("execute", options, checker))
                    made["checker"] = checker
                    return checker

            def setup_expectations(
                *, options: protocols.RunOptions[protocols.Scenario]
            ) -> protocols.ExpectationsMaker[protocols.Scenario]:
                def make_expectations() -> protocols.Expectations[protocols.Scenario]:
                    @dataclasses.dataclass(frozen=True, kw_only=True)
                    class Expectations(stubs.StubExpectations[protocols.Scenario]):
                        def check(
                            self, *, notice_checker: protocols.NoticeChecker[protocols.Scenario]
                        ) -> None:
                            called.append(("check", notice_checker, self))

                    expectations = Expectations()
                    called.append(("make_expectations", expectations))
                    made["expectations"] = expectations
                    return expectations

                called.append(("setup", options))
                return make_expectations

            runner = Runner.create(
                config=stubs.StubRunnerConfig(),
                root_dir=tmp_path,
                scenario_maker=scenarios.Scenario.create,
                scenario_runs_maker=scenarios.ScenarioRuns.create,
            )
            assert not runner.runs.has_runs

            runner.run_and_check(setup_expectations)
            assert called == [
                ("determine_options", made["options"]),
                ("setup", made["options"]),
                ("execute", made["options"], made["checker"]),
                ("make_expectations", made["expectations"]),
                ("check", made["checker"], made["expectations"]),
            ]

            assert runner.runs.has_runs
            assert (
                "\n".join(runner.runs.for_report())
                == textwrap.dedent("""
                :: Run 1
                   | > stubrun .
                   | | exit_code=1
                   | | stdout: one
                   | | stdout: two
                   | | stderr:
                """).strip()
            )

        def test_it_does_followup_with_same_options_and_expectations(
            self, tmp_path: pathlib.Path
        ) -> None:
            called: list[object] = []

            class Made(TypedDict):
                options: NotRequired[protocols.RunOptions[protocols.Scenario]]
                checker1: NotRequired[protocols.NoticeChecker[protocols.Scenario]]
                checker2: NotRequired[protocols.NoticeChecker[protocols.Scenario]]
                expectations: NotRequired[protocols.Expectations[protocols.Scenario]]

            made: Made = {}

            @dataclasses.dataclass(frozen=True, kw_only=True)
            class Runner(scenarios.ScenarioRunner[protocols.Scenario]):
                def determine_options(self) -> protocols.RunOptions[protocols.Scenario]:
                    # Enable followup!
                    options = super().determine_options().clone(do_followup=True)
                    called.append(("determine_options", options))
                    assert "options" not in made
                    made["options"] = options
                    return options

                def execute_static_checking(
                    self, options: protocols.RunOptions[protocols.Scenario]
                ) -> protocols.NoticeChecker[protocols.Scenario]:
                    if "checker1" not in made:
                        checker = stubs.StubNoticeChecker(
                            result=stubs.StubRunResult(exit_code=1, stdout="one\ntwo"),
                            runner=stubs.StubProgramRunner(options=options),
                        )
                        made["checker1"] = checker
                    elif "checker2" not in made:
                        checker = stubs.StubNoticeChecker(
                            result=stubs.StubRunResult(
                                exit_code=0, stdout="three\nfour", stderr="five"
                            ),
                            runner=stubs.StubProgramRunner(options=options),
                        )
                        made["checker2"] = checker
                    else:
                        assert "checker2" not in made

                    called.append(("execute", options, checker))
                    return checker

            def setup_expectations(
                *, options: protocols.RunOptions[protocols.Scenario]
            ) -> protocols.ExpectationsMaker[protocols.Scenario]:
                def make_expectations() -> protocols.Expectations[protocols.Scenario]:
                    @dataclasses.dataclass(frozen=True, kw_only=True)
                    class Expectations(stubs.StubExpectations[protocols.Scenario]):
                        def check(
                            self, *, notice_checker: protocols.NoticeChecker[protocols.Scenario]
                        ) -> None:
                            called.append(("check", notice_checker, self))

                    expectations = Expectations()
                    called.append(("make_expectations", expectations))
                    assert "expectations" not in made
                    made["expectations"] = expectations
                    return expectations

                called.append(("setup", options))
                return make_expectations

            runner = Runner.create(
                config=stubs.StubRunnerConfig(),
                root_dir=tmp_path,
                scenario_maker=scenarios.Scenario.create,
                scenario_runs_maker=scenarios.ScenarioRuns.create,
            )
            assert not runner.runs.has_runs

            runner.run_and_check(setup_expectations)
            assert called == [
                ("determine_options", made["options"]),
                ("setup", made["options"]),
                ("execute", made["options"], made["checker1"]),
                ("make_expectations", made["expectations"]),
                ("check", made["checker1"], made["expectations"]),
                ("execute", made["options"], made["checker2"]),
                ("check", made["checker2"], made["expectations"]),
            ]

            assert runner.runs.has_runs
            assert (
                "\n".join(runner.runs.for_report())
                == textwrap.dedent("""
                :: Run 1
                   | > stubrun .
                   | | exit_code=1
                   | | stdout: one
                   | | stdout: two
                   | | stderr:
                :: Run 2
                   | > [followup run]
                   | | exit_code=0
                   | | stdout: three
                   | | stdout: four
                   | | stderr: five
                """).strip()
            )

        def test_it_catches_and_re_raises_expectations_check_failing(
            self, runner: protocols.ScenarioRunner[protocols.Scenario]
        ) -> None:
            class ComputerSaysNo(Exception):
                pass

            error = ComputerSaysNo("NOPE!")

            def setup_expectations(
                *, options: protocols.RunOptions[protocols.Scenario]
            ) -> protocols.ExpectationsMaker[protocols.Scenario]:
                @dataclasses.dataclass(frozen=True, kw_only=True)
                class Expectations(stubs.StubExpectations[protocols.Scenario]):
                    def check(
                        self, *, notice_checker: protocols.NoticeChecker[protocols.Scenario]
                    ) -> None:
                        raise error

                return Expectations

            assert not runner.runs.has_runs

            with pytest.raises(ComputerSaysNo) as e:
                runner.run_and_check(setup_expectations)
            assert e.value is error

            assert runner.runs.has_runs
            assert (
                "\n".join(runner.runs.for_report())
                == textwrap.dedent("""
                :: Run 1
                   | > stubrun .
                   | | exit_code=0
                   | | stdout:
                   | | stderr:
                   | !!! <ComputerSaysNo> NOPE!
                """).strip()
            )
