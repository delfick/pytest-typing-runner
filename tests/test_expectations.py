import dataclasses
import pathlib

import pytest
from pytest_typing_runner_test_driver import stubs

from pytest_typing_runner import expectations, notice_changers, notices, protocols, scenarios


class TestExpectations:
    def test_it_has_attributes(self) -> None:
        program_notices = notices.ProgramNotices()

        expected = expectations.Expectations[protocols.Scenario](
            expect_fail=True, expect_stderr="stuff and things", expect_notices=program_notices
        )

        assert expected.expect_fail
        assert expected.expect_stderr == "stuff and things"
        assert expected.expect_notices is program_notices

    def test_it_has_defaults(self) -> None:
        expected = expectations.Expectations[protocols.Scenario]()

        assert not expected.expect_fail
        assert expected.expect_stderr == ""
        assert isinstance(expected.expect_notices, notices.ProgramNotices)

    def test_it_passes_on_expect_notices_to_notice_checker(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runner.determine_options()
        program_runner = options.make_program_runner(options=options)

        called: list[object] = []

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class NoticeChecker(stubs.StubNoticeChecker[scenarios.Scenario]):
            def check(self, expected_notices: protocols.ProgramNotices, /) -> None:
                called.append(("check", expected_notices))

        notice_checker = NoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="", stdout=""), runner=program_runner
        )
        expected_notices = notice_changers.ModifyFile(
            location=tmp_path / "one",
            must_exist=False,
            change=notice_changers.ModifyLine(
                name_or_line=2,
                line_must_exist=False,
                change=notice_changers.AppendToLine(
                    notices_maker=lambda ln: [ln.generate_notice(msg="n1")]
                ),
            ),
        )(runner.generate_program_notices())

        expected = expectations.Expectations[scenarios.Scenario](expect_notices=expected_notices)
        assert called == []

        expected.check(notice_checker=notice_checker)
        assert called == [("check", expected_notices)]

    def test_it_complains_if_stderr_does_not_match(self, tmp_path: pathlib.Path) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runner.determine_options()
        program_runner = options.make_program_runner(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="hello", stdout=""),
            runner=program_runner,
        )

        expected = expectations.Expectations[scenarios.Scenario](
            expect_stderr="hi", expect_notices=runner.generate_program_notices()
        )

        with pytest.raises(AssertionError) as e:
            expected.check(notice_checker=notice_checker)

        assert str(e.value) == "Expected stderr in result (hello) to match expectations (hi)"

    def test_it_complains_if_expect_fail_but_got_zero_exit_code(
        self, tmp_path: pathlib.Path
    ) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runner.determine_options()
        program_runner = options.make_program_runner(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="", stdout=""),
            runner=program_runner,
        )

        expected = expectations.Expectations[scenarios.Scenario](
            expect_fail=True, expect_notices=runner.generate_program_notices()
        )

        with pytest.raises(AssertionError) as e:
            expected.check(notice_checker=notice_checker)

        assert str(e.value) == "Expected exit code from result (0) to be non zero"

    def test_it_complains_if_do_not_expect_fail_but_got_non_zero_exit_code(
        self, tmp_path: pathlib.Path
    ) -> None:
        config = stubs.StubRunnerConfig()
        runner = scenarios.ScenarioRunner.create(
            config=config,
            root_dir=tmp_path,
            scenario_maker=scenarios.Scenario.create,
            scenario_runs_maker=scenarios.ScenarioRuns.create,
        )
        options = runner.determine_options()
        program_runner = options.make_program_runner(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=99, stderr="", stdout=""),
            runner=program_runner,
        )

        expected = expectations.Expectations[scenarios.Scenario](
            expect_fail=False, expect_notices=runner.generate_program_notices()
        )

        with pytest.raises(AssertionError) as e:
            expected.check(notice_checker=notice_checker)

        assert str(e.value) == "Expected exit code from result (99) to be zero"
