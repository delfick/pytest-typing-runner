import pathlib
import textwrap
from typing import Protocol

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import notice_changers, notices, protocols, runners, scenarios


class NoticeCheckerMaker(Protocol):
    def __call__(
        self,
        *,
        result: protocols.RunResult,
        runner: protocols.ProgramRunner[protocols.Scenario],
        run_options: protocols.RunOptions[protocols.Scenario],
    ) -> protocols.NoticeChecker[protocols.Scenario]: ...


class TestMypyChecker:
    @pytest.fixture
    def checker_maker(self) -> NoticeCheckerMaker:
        return runners.MypyChecker[protocols.Scenario]

    def test_it_can_check_successful_mypy_result(
        self, tmp_path: pathlib.Path, checker_maker: NoticeCheckerMaker
    ) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner[protocols.Scenario].create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        result = stubs.StubRunResult(
            exit_code=0,
            stdout=textwrap.dedent("""
            main.py:3: note: Revealed type is "builtins.int"
            Success: no issues found in 2 source files
        """).strip(),
        )

        checker = checker_maker(result=result, run_options=options, runner=program_runner)

        expected_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={"main.py": {3: [notices.ProgramNotice.reveal_msg("builtins.int")]}},
        )(runner.generate_program_notices())
        checker.check(expected_notices)

        expected_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={"main.py": {5: [notices.ProgramNotice.reveal_msg("builtins.int")]}},
        )(expected_notices)

        with pytest.raises(AssertionError) as e:
            checker.check(expected_notices)

        assert (
            str(e.value).strip()
            == textwrap.dedent("""
            > main.py
              | ✓ 3: severity=note:: Revealed type is "builtins.int"
              | ✘ 5:
              | ✘ !! GOT  !! <NONE>
              |   !! WANT !! severity=note:: Revealed type is "builtins.int"
            """).strip()
        )

    def test_it_can_check_error_mypy_result(
        self, tmp_path: pathlib.Path, checker_maker: NoticeCheckerMaker
    ) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner[protocols.Scenario].create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        result = stubs.StubRunResult(
            exit_code=1,
            stdout=textwrap.dedent("""
            main.py:3: note: Revealed type is "builtins.int"
            main.py:7: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]
            Found 1 error in 1 file (checked 2 source files)
        """).strip(),
        )

        checker = checker_maker(result=result, run_options=options, runner=program_runner)

        expected_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={
                "main.py": {
                    3: [notices.ProgramNotice.reveal_msg("builtins.int")],
                    7: [
                        (
                            notices.ErrorSeverity("assignment"),
                            'Incompatible types in assignment (expression has type "str", variable has type "int")',
                        )
                    ],
                }
            },
        )(runner.generate_program_notices())
        checker.check(expected_notices)

        expected_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={"main.py": {5: [notices.ProgramNotice.reveal_msg("builtins.int")]}},
        )(expected_notices)

        with pytest.raises(AssertionError) as e:
            checker.check(expected_notices)

        assert (
            str(e.value).strip()
            == textwrap.dedent("""
            > main.py
              | ✓ 3: severity=note:: Revealed type is "builtins.int"
              | ✘ 5:
              | ✘ !! GOT  !! <NONE>
              |   !! WANT !! severity=note:: Revealed type is "builtins.int"
              | ✓ 7: severity=error[assignment]:: Incompatible types in assignment (expression has type "str", variable has type "int")
            """).strip()
        )


class TestDMypyChecker:
    @pytest.fixture
    def checker_maker(self) -> NoticeCheckerMaker:
        return runners.DaemonMypyChecker[protocols.Scenario]

    def test_it_can_check_successful_mypy_result(
        self, tmp_path: pathlib.Path, checker_maker: NoticeCheckerMaker
    ) -> None:
        TestMypyChecker().test_it_can_check_successful_mypy_result(tmp_path, checker_maker)

    def test_it_can_check_error_mypy_result(
        self, tmp_path: pathlib.Path, checker_maker: NoticeCheckerMaker
    ) -> None:
        TestMypyChecker().test_it_can_check_error_mypy_result(tmp_path, checker_maker)

    def test_it_tests_if_daemon_restarted_or_not(
        self, tmp_path: pathlib.Path, checker_maker: NoticeCheckerMaker
    ) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner[protocols.Scenario].create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        expected_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={"main.py": {3: [notices.ProgramNotice.reveal_msg("builtins.int")]}},
        )(runner.generate_program_notices())

        result = stubs.StubRunResult(
            exit_code=1,
            stdout=textwrap.dedent("""
            main.py:3: note: Revealed type is "builtins.int"
            Success: no issues found in 2 source files
        """).strip(),
        )

        checker = checker_maker(result=result, run_options=options, runner=program_runner)
        runner.scenario.expects.daemon_restarted = False
        checker.check(expected_notices)

        result = stubs.StubRunResult(
            exit_code=1,
            stdout=textwrap.dedent("""
            Restarting: configuration changed
            Daemon stopped
            Daemon started
            main.py:3: note: Revealed type is "builtins.int"
            Success: no issues found in 2 source files
        """).strip(),
        )

        with pytest.raises(AssertionError, match="Did not expect the daemon to restart"):
            checker = checker_maker(result=result, run_options=options, runner=program_runner)
            runner.scenario.expects.daemon_restarted = False
            checker.check(expected_notices)

        runner.scenario.expects.daemon_restarted = True
        checker.check(expected_notices)
        # Should be flipped as a result
        assert not runner.scenario.expects.daemon_restarted

        result = stubs.StubRunResult(
            exit_code=1,
            stdout=textwrap.dedent("""
            Daemon started
            main.py:3: note: Revealed type is "builtins.int"
            Success: no issues found in 2 source files
        """).strip(),
        )
        checker = checker_maker(result=result, run_options=options, runner=program_runner)
        runner.scenario.expects.daemon_restarted = False
        checker.check(expected_notices)
        # should stay false
        assert not runner.scenario.expects.daemon_restarted

        with pytest.raises(AssertionError, match="Expect the daemon to have restarted"):
            checker = checker_maker(result=result, run_options=options, runner=program_runner)
            runner.scenario.expects.daemon_restarted = True
            checker.check(expected_notices)
