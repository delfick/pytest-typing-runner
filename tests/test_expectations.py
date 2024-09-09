import dataclasses
import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import matchers, stubs

from pytest_typing_runner import (
    expectations,
    notice_changers,
    notices,
    protocols,
    runners,
    scenarios,
)


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
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        called: list[object] = []

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class NoticeChecker(stubs.StubNoticeChecker[scenarios.Scenario]):
            def check(self, expected_notices: protocols.ProgramNotices, /) -> None:
                called.append(("check", expected_notices))

        notice_checker = NoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="", stdout=""),
            runner=program_runner,
            run_options=options,
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
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="hello", stdout=""),
            run_options=options,
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
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=0, stderr="", stdout=""),
            run_options=options,
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
        options = runners.RunOptions.create(runner)
        program_runner = options.program_runner_maker(options=options)

        notice_checker = stubs.StubNoticeChecker(
            result=stubs.StubRunResult(exit_code=99, stderr="", stdout=""),
            run_options=options,
            runner=program_runner,
        )

        expected = expectations.Expectations[scenarios.Scenario](
            expect_fail=False, expect_notices=runner.generate_program_notices()
        )

        with pytest.raises(AssertionError) as e:
            expected.check(notice_checker=notice_checker)

        assert str(e.value) == "Expected exit code from result (99) to be zero"


class TestNormaliseNotices:
    def test_it_makes_no_changes_if_no_multiline_messages(self, tmp_path: pathlib.Path) -> None:
        l1 = tmp_path / "1"
        l2 = tmp_path / "2"

        program_notices = notices.ProgramNotices()
        f1 = program_notices.generate_notices_for_location(l1)
        f1l1 = f1.generate_notices_for_line(1)
        n1 = f1l1.generate_notice(msg="a")
        n2 = f1l1.generate_notice(msg="b")

        f2 = program_notices.generate_notices_for_location(l2)
        f2l4 = f2.generate_notices_for_line(4)
        n3 = f2l4.generate_notice(msg="c", severity=notices.ErrorSeverity("arg-type"))
        n4 = f2l4.generate_notice(msg="d")
        f2l5 = f2.generate_notices_for_line(5)
        n5 = f2l5.generate_notice(msg="e")
        n6 = f2l5.generate_notice(msg="f", severity=notices.ErrorSeverity("assignment"))

        assert list(expectations.normalise_notices([n1, n2, n3, n4, n5, n6])) == [
            matchers.MatchNote(location=l1, line_number=1, msg="a"),
            matchers.MatchNote(location=l1, line_number=1, msg="b"),
            matchers.MatchNotice(
                location=l2, line_number=4, severity=notices.ErrorSeverity("arg-type"), msg="c"
            ),
            matchers.MatchNote(location=l2, line_number=4, msg="d"),
            matchers.MatchNotice(
                location=l2, line_number=5, severity=notices.ErrorSeverity("assignment"), msg="f"
            ),
            matchers.MatchNote(location=l2, line_number=5, msg="e"),
        ]

    def test_it_splits_multiline_notices(self, tmp_path: pathlib.Path) -> None:
        l1 = tmp_path / "1"
        l2 = tmp_path / "2"

        program_notices = notices.ProgramNotices()
        f1 = program_notices.generate_notices_for_location(l1)
        f1l1 = f1.generate_notices_for_line(1)
        n1 = f1l1.generate_notice(msg="a\nb\nc")
        n2 = f1l1.generate_notice(msg="b")

        f2 = program_notices.generate_notices_for_location(l2)
        f2l4 = f2.generate_notices_for_line(4)
        n3 = f2l4.generate_notice(msg="c\nb\na", severity=notices.ErrorSeverity("arg-type"))
        n4 = f2l4.generate_notice(msg="f")
        f2l5 = f2.generate_notices_for_line(5)
        n5 = f2l5.generate_notice(msg="g\nf")
        n6 = f2l5.generate_notice(msg="h", severity=notices.ErrorSeverity("assignment"))

        assert list(expectations.normalise_notices([n1, n2, n3, n4, n5, n6])) == [
            matchers.MatchNote(location=l1, line_number=1, msg="a"),
            matchers.MatchNote(location=l1, line_number=1, msg="b"),
            matchers.MatchNote(location=l1, line_number=1, msg="c"),
            matchers.MatchNote(location=l1, line_number=1, msg="b"),
            matchers.MatchNotice(
                location=l2, line_number=4, severity=notices.ErrorSeverity("arg-type"), msg="c"
            ),
            matchers.MatchNotice(
                location=l2, line_number=4, severity=notices.ErrorSeverity("arg-type"), msg="b"
            ),
            matchers.MatchNotice(
                location=l2, line_number=4, severity=notices.ErrorSeverity("arg-type"), msg="a"
            ),
            matchers.MatchNote(location=l2, line_number=4, msg="f"),
            matchers.MatchNotice(
                location=l2, line_number=5, severity=notices.ErrorSeverity("assignment"), msg="h"
            ),
            matchers.MatchNote(location=l2, line_number=5, msg="g"),
            matchers.MatchNote(location=l2, line_number=5, msg="f"),
        ]


class TestCompareNotices:
    def test_it_says_two_empty_diff_is_fine(self) -> None:
        expectations.compare_notices(notices.DiffNotices(by_file={}))

    def test_it_makes_no_error_if_no_difference(self) -> None:
        def note(path: str, line_number: int, msg: str) -> protocols.ProgramNotice:
            return notices.ProgramNotice.create(
                location=pathlib.Path(path),
                line_number=line_number,
                severity=notices.NoteSeverity(),
                msg=msg,
            )

        def error(
            path: str, line_number: int, error_type: str, msg: str
        ) -> protocols.ProgramNotice:
            return notices.ProgramNotice.create(
                location=pathlib.Path(path),
                line_number=line_number,
                severity=notices.ErrorSeverity(error_type),
                msg=msg,
            )

        diff = notices.DiffNotices(
            by_file={
                (path := "one"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 1): (
                            [
                                note(path, line_number, "one"),
                            ],
                            [
                                note(path, line_number, "one"),
                            ],
                        )
                    },
                ),
                (path := "two"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 10): (
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                        )
                    },
                ),
            }
        )

        expectations.compare_notices(diff)

    def test_it_shows_what_is_same_and_not_same_when_is_different(self) -> None:
        def note(
            path: str,
            line_number: int,
            msg: str,
            msg_maker: protocols.NoticeMsgMaker = notices.PlainMsg.create,
        ) -> protocols.ProgramNotice:
            return notices.ProgramNotice.create(
                location=pathlib.Path(path),
                line_number=line_number,
                severity=notices.NoteSeverity(),
                msg=msg_maker(pattern=msg),
            )

        def error(
            path: str,
            line_number: int,
            error_type: str,
            msg: str,
            msg_maker: protocols.NoticeMsgMaker = notices.PlainMsg.create,
        ) -> protocols.ProgramNotice:
            return notices.ProgramNotice.create(
                location=pathlib.Path(path),
                line_number=line_number,
                severity=notices.ErrorSeverity(error_type),
                msg=msg_maker(pattern=msg),
            )

        diff = notices.DiffNotices(
            by_file={
                (path := "one"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 1): (
                            [
                                note(path, line_number, "one\ntwo\nthree"),
                            ],
                            [
                                note(path, line_number, "one"),
                                note(path, line_number, "two"),
                                note(path, line_number, "three"),
                            ],
                        ),
                        (line_number := 5): (
                            [],
                            [
                                note(path, line_number, "four"),
                            ],
                        ),
                        (line_number := 6): (
                            [
                                error(path, line_number, "arg-type", "hi"),
                                error(path, line_number, "assignment", "three"),
                            ],
                            [
                                error(path, line_number, "arg-type", "hi"),
                            ],
                        ),
                        (line_number := 10): (
                            [
                                note(path, line_number, "four"),
                                note(path, line_number, "fur"),
                            ],
                            [
                                note(
                                    path, line_number, "f.{2}r", msg_maker=notices.RegexMsg.create
                                ),
                                note(
                                    path, line_number, "f.{2}r", msg_maker=notices.RegexMsg.create
                                ),
                            ],
                        ),
                    },
                ),
                (path := "two"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 1): (
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                        )
                    },
                ),
                (path := "three"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 20): (
                            [],
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                        ),
                        (line_number := 21): (
                            [],
                            [
                                note(path, line_number, "stuff"),
                            ],
                        ),
                    },
                ),
                (path := "three/four"): notices.DiffFileNotices(
                    by_line_number={
                        (line_number := 20): (
                            [
                                error(path, line_number, "arg-type", "two"),
                            ],
                            [],
                        ),
                        (line_number := 21): (
                            [
                                note(path, line_number, "stuff"),
                            ],
                            [],
                        ),
                    },
                ),
            }
        )

        with pytest.raises(AssertionError) as e:
            expectations.compare_notices(diff)

        expected = textwrap.dedent("""
        > one
          | ✘ 1:
          | ✓ severity=note:: one
          | ✘ !! GOT  !! severity=note:: two
          |   !! WANT !! severity=note:: three
          | ✘ !! GOT  !! severity=note:: three
          |   !! WANT !! severity=note:: two
          | ✘ 5:
          | ✘ !! GOT  !! <NONE>
          |   !! WANT !! severity=note:: four
          | ✘ 6:
          | ✓ severity=error[arg-type]:: hi
          | ✘ !! GOT  !! severity=error[assignment]:: three
          |   !! WANT !! <NONE>
          | ✘ 10:
          | ✓ severity=note:: four
          | ✘ !! GOT  !! severity=note:: fur
          |   !! WANT !! severity=note:: f.{2}r
        > three
          | ✘ 20:
          | ✘ !! GOT  !! <NONE>
          |   !! WANT !! severity=error[arg-type]:: two
          | ✘ 21:
          | ✘ !! GOT  !! <NONE>
          |   !! WANT !! severity=note:: stuff
        > three/four
          | ✘ 20:
          | ✘ !! GOT  !! severity=error[arg-type]:: two
          |   !! WANT !! <NONE>
          | ✘ 21:
          | ✘ !! GOT  !! severity=note:: stuff
          |   !! WANT !! <NONE>
        > two
          | ✓ 1: severity=error[arg-type]:: two
          """).strip()

        assert str(e.value).strip() == expected
