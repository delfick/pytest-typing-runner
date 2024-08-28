import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import protocols, scenarios


class TestRunCleaners:
    def test_it_can_add_and_iterate_cleaners(self) -> None:
        cleaners = scenarios.RunCleaners()
        called: list[str] = []

        def make_cleaner(msg: str) -> protocols.RunCleaner:
            def clean() -> None:
                called.append(msg)

            return clean

        cleaners.add("b", make_cleaner("1"))
        cleaners.add("c", make_cleaner("3"))
        cleaners.add("a", make_cleaner("2"))

        all_cleans = iter(cleaners)
        assert called == []

        next(all_cleans)()
        assert called == ["1"]

        next(all_cleans)()
        assert called == ["1", "3"]

        next(all_cleans)()
        assert called == ["1", "3", "2"]

        with pytest.raises(StopIteration):
            next(all_cleans)

    def test_it_can_override_cleaners(self) -> None:
        cleaners = scenarios.RunCleaners()
        called: list[str] = []

        def make_cleaner(msg: str) -> protocols.RunCleaner:
            def clean() -> None:
                called.append(msg)

            return clean

        cleaners.add("b", make_cleaner("1"))
        cleaners.add("c", make_cleaner("3"))
        cleaners.add("a", make_cleaner("2"))
        cleaners.add("b", make_cleaner("4"))

        all_cleans = iter(cleaners)
        assert called == []

        next(all_cleans)()
        assert called == ["4"]

        next(all_cleans)()
        assert called == ["4", "3"]

        next(all_cleans)()
        assert called == ["4", "3", "2"]

        with pytest.raises(StopIteration):
            next(all_cleans)


class TestScenarioRun:
    @pytest.fixture
    def options(self, tmp_path: pathlib.Path) -> protocols.RunOptions[protocols.Scenario]:
        scenario_runner = scenarios.ScenarioRunner[protocols.Scenario].create(
            config=stubs.StubRunnerConfig(),
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        return scenario_runner.determine_options()

    def test_it_has_attributes(self, options: protocols.RunOptions[protocols.Scenario]) -> None:
        notice_checker = options.make_program_runner(options=options).run()
        scenario_run = scenarios.ScenarioRun(
            is_first=True,
            is_followup=False,
            checker=notice_checker,
            expectation_error=None,
            file_modifications=[("one", "two"), ("three", "four")],
        )

        assert scenario_run.is_first == True
        assert scenario_run.is_followup == False
        assert scenario_run.checker is notice_checker
        assert scenario_run.expectation_error is None
        assert scenario_run.file_modifications == [("one", "two"), ("three", "four")]

    def test_it_can_hold_an_expectation_error(
        self, options: protocols.RunOptions[protocols.Scenario]
    ) -> None:
        error = Exception("Computer says no")
        notice_checker = options.make_program_runner(options=options).run()
        scenario_run = scenarios.ScenarioRun(
            is_first=False,
            is_followup=True,
            checker=notice_checker,
            expectation_error=error,
            file_modifications=[],
        )

        assert scenario_run.expectation_error is error

    class TestForReport:
        def test_it_prints_each_file_modification(
            self, options: protocols.RunOptions[protocols.Scenario]
        ) -> None:
            notice_checker = options.make_program_runner(options=options).run()
            scenario_run = scenarios.ScenarioRun(
                is_first=True,
                is_followup=False,
                checker=notice_checker,
                expectation_error=None,
                file_modifications=[("P1", "A1"), ("P2___as", "A2aaai")],
            )

            got = "\n".join(scenario_run.for_report())
            assert (
                got
                == textwrap.dedent("""
                * A1        : P1
                * A2aaai    : P2___as
                > stubrun .
                | exit_code=0
                | stdout:
                | stderr:
                """).strip()
            )

        def test_it_prints_runner_command_plus_args_and_check_paths(
            self, options: protocols.RunOptions[protocols.Scenario]
        ) -> None:
            options.args.clear()
            options.args.extend(["a1", "a2"])
            options.check_paths.clear()
            options.check_paths.extend(["c1", "c2"])
            notice_checker = options.make_program_runner(options=options).run()

            scenario_run = scenarios.ScenarioRun(
                is_first=True,
                is_followup=False,
                checker=notice_checker,
                expectation_error=None,
                file_modifications=[],
            )

            got = "\n".join(scenario_run.for_report())
            assert (
                got
                == textwrap.dedent("""
                > stubrun a1 a2 c1 c2
                | exit_code=0
                | stdout:
                | stderr:
                """).strip()
            )

        def test_it_prints_that_it_is_followup_if_followup(
            self, options: protocols.RunOptions[protocols.Scenario]
        ) -> None:
            notice_checker = options.make_program_runner(options=options).run()

            scenario_run = scenarios.ScenarioRun(
                is_first=False,
                is_followup=True,
                checker=notice_checker,
                expectation_error=None,
                file_modifications=[],
            )

            got = "\n".join(scenario_run.for_report())
            assert (
                got
                == textwrap.dedent("""
                > [followup run]
                | exit_code=0
                | stdout:
                | stderr:
                """).strip()
            )

        def test_it_prints_expectation_error(
            self, options: protocols.RunOptions[protocols.Scenario]
        ) -> None:
            notice_checker = options.make_program_runner(options=options).run()

            class ComputerSaysNo(Exception):
                def __str__(self) -> str:
                    return "NO!"

            scenario_run = scenarios.ScenarioRun(
                is_first=False,
                is_followup=True,
                checker=notice_checker,
                expectation_error=ComputerSaysNo(),
                file_modifications=[],
            )

            got = "\n".join(scenario_run.for_report())
            assert (
                got
                == textwrap.dedent("""
                > [followup run]
                | exit_code=0
                | stdout:
                | stderr:
                !!! <ComputerSaysNo> NO!
                """).strip()
            )

        def test_it_prints_stdout_and_stderr_and_exit_code(
            self, options: protocols.RunOptions[protocols.Scenario]
        ) -> None:
            runner = options.make_program_runner(options=options)
            notice_checker = stubs.StubNoticeChecker(
                runner=runner,
                result=stubs.StubRunResult(
                    exit_code=2,
                    stdout="one\ntwo  \nthree four\nfive::",
                    stderr="six\nseven eight\nnine  ",
                ),
            )

            scenario_run = scenarios.ScenarioRun(
                is_first=False,
                is_followup=True,
                checker=notice_checker,
                expectation_error=None,
                file_modifications=[],
            )

            got = "\n".join(scenario_run.for_report())
            assert (
                got
                == textwrap.dedent("""
                > [followup run]
                | exit_code=2
                | stdout: one
                | stdout: two
                | stdout: three four
                | stdout: five::
                | stderr: six
                | stderr: seven eight
                | stderr: nine
                """).strip()
            )


class TestScenarioRuns:
    @pytest.fixture
    def runner(self, tmp_path: pathlib.Path) -> protocols.ScenarioRunner[protocols.Scenario]:
        return scenarios.ScenarioRunner[protocols.Scenario].create(
            config=stubs.StubRunnerConfig(),
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )

    def test_it_has_create_classmethod(
        self, runner: scenarios.ScenarioRunner[protocols.Scenario]
    ) -> None:
        runs = scenarios.ScenarioRuns.create(scenario=runner.scenario)
        assert isinstance(runs, scenarios.ScenarioRuns)
        assert runs.scenario is runner.scenario

    def test_it_has_a_scenario(self, runner: protocols.ScenarioRunner[protocols.Scenario]) -> None:
        options = runner.determine_options()
        runs = scenarios.ScenarioRuns(scenario=options.scenario_runner.scenario)
        assert runs.scenario is options.scenario_runner.scenario

    def test_it_can_be_given_runs(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runner.determine_options()
        runs = scenarios.ScenarioRuns(scenario=options.scenario_runner.scenario)
        assert not runs.has_runs

        assert "\n".join(runs.for_report()) == ""

        options = runner.determine_options()
        notice_checker = options.make_program_runner(options=options).run()
        runs.add_run(checker=notice_checker, expectation_error=None)
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
                :: Run 1
                   | > stubrun .
                   | | exit_code=0
                   | | stdout:
                   | | stderr:
                """).strip()
        )

        options = runner.determine_options()
        notice_checker = options.make_program_runner(options=options).run()
        runs.add_run(checker=notice_checker, expectation_error=None)
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
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
        )

        options = runner.determine_options()
        options.args.append("one")
        options.check_paths.append("two")
        notice_checker = stubs.StubNoticeChecker(
            runner=options.make_program_runner(options=options),
            result=stubs.StubRunResult(
                exit_code=2,
                stdout="one\ntwo  \nthree four\nfive::",
                stderr="six\nseven eight\nnine  ",
            ),
        )

        runs.add_run(checker=notice_checker, expectation_error=ValueError("nope"))
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
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
            :: Run 3
               | > stubrun one . two
               | | exit_code=2
               | | stdout: one
               | | stdout: two
               | | stdout: three four
               | | stdout: five::
               | | stderr: six
               | | stderr: seven eight
               | | stderr: nine
               | !!! <ValueError> nope
                """).strip()
        )

    def test_it_prepare_file_modifications(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runner.determine_options()
        runs = scenarios.ScenarioRuns(scenario=options.scenario_runner.scenario)
        assert not runs.has_runs

        assert "\n".join(runs.for_report()) == ""

        options = runner.determine_options()
        runs.add_file_modification("some/path", "create")
        runs.add_file_modification("some/other/path", "change")
        notice_checker = options.make_program_runner(options=options).run()
        runs.add_run(checker=notice_checker, expectation_error=None)
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
                :: Run 1
                   | * create    : some/path
                   | * change    : some/other/path
                   | > stubrun .
                   | | exit_code=0
                   | | stdout:
                   | | stderr:
                """).strip()
        )

        options = runner.determine_options()
        notice_checker = options.make_program_runner(options=options).run()
        runs.add_run(checker=notice_checker, expectation_error=None)
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
               :: Run 1
                  | * create    : some/path
                  | * change    : some/other/path
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
        )

        options = runner.determine_options()
        options.args.append("one")
        notice_checker = options.make_program_runner(options=options).run()

        runs.add_file_modification("some/path", "remove")
        runs.add_file_modification("other/blah", "change")
        runs.add_run(checker=notice_checker, expectation_error=None)
        assert runs.has_runs

        got = "\n".join(runs.for_report())
        assert (
            got
            == textwrap.dedent("""
               :: Run 1
                  | * create    : some/path
                  | * change    : some/other/path
                  | > stubrun .
                  | | exit_code=0
                  | | stdout:
                  | | stderr:
               :: Run 2
                  | > [followup run]
                  | | exit_code=0
                  | | stdout:
                  | | stderr:
               :: Run 3
                  | * remove    : some/path
                  | * change    : other/blah
                  | > stubrun one .
                  | | exit_code=0
                  | | stdout:
                  | | stderr:
                """).strip()
        )