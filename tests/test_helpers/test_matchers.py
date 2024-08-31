import pathlib
from typing import Any

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notices, protocols


@pytest.fixture
def notice(tmp_path: pathlib.Path) -> protocols.ProgramNotice:
    return notices.ProgramNotice.create(
        location=tmp_path, line_number=10, severity=notices.NoteSeverity(), msg="hello"
    )


class TestMatchNotice:
    def test_it_can_match_a_notice(
        self, tmp_path: pathlib.Path, notice: protocols.ProgramNotice
    ) -> None:
        combinations: list[
            tuple[matchers.MatchNotice._Compare, matchers.MatchNotice._Compare | None, bool]
        ] = [
            ({"msg": "hello"}, None, True),
            ({"line_number": 20}, None, True),
            ({"col": 20}, None, True),
            ({"col": None}, None, True),
            ({"location": tmp_path / "one"}, None, True),
            ({"severity": notices.ErrorSeverity("arg-type")}, None, True),
            (
                {
                    "msg": "hello",
                    "line_number": 20,
                    "col": 3,
                    "location": tmp_path / "two",
                    "severity": notices.ErrorSeverity("arg-type"),
                },
                None,
                True,
            ),
            ({"msg": "hello"}, {"msg": "hello", "line_number": 10}, True),
            ({"msg": "hello", "line_number": 20}, {"msg": "hello", "line_number": 10}, False),
            (
                {"display": "severity=note:: blah"},
                {"msg": "blah", "severity": notices.NoteSeverity(), "col": None},
                True,
            ),
            (
                {"display": "severity=note:: blah"},
                {"msg": "meh", "severity": notices.NoteSeverity(), "col": None},
                False,
            ),
        ]

        for left, right, expect in combinations:
            if right is None:
                right = left

            clone_args: dict[str, Any] = dict(right)
            if expect:
                assert matchers.MatchNotice(**left) == notice.clone(**clone_args)
            else:
                assert matchers.MatchNotice(**left) != notice.clone(**clone_args)


class TestMatchNote:
    def test_it_checks_note_severity(
        self, tmp_path: pathlib.Path, notice: protocols.ProgramNotice
    ) -> None:
        notice = notice.clone(severity=notices.NoteSeverity())

        combinations: list[
            tuple[
                matchers.MatchNote._Compare, protocols.ProgramNoticeCloneAndMsgKwargs | None, bool
            ]
        ] = [
            ({"msg": "hello"}, None, True),
            (
                {"msg": "hello"},
                {"severity": notices.ErrorSeverity("assignment"), "msg": "hello"},
                False,
            ),
            ({"line_number": 20}, None, True),
            ({"col": 20}, None, True),
            ({"col": None}, None, True),
            ({"location": tmp_path / "one"}, None, True),
            (
                {"msg": "hello", "line_number": 20, "col": 3, "location": tmp_path / "two"},
                None,
                True,
            ),
            ({"msg": "hello"}, {"msg": "hello", "line_number": 10}, True),
            ({"msg": "hello", "line_number": 20}, {"msg": "hello", "line_number": 10}, False),
        ]

        for left, right, expect in combinations:
            if right is None:
                clone_args: dict[str, Any] = dict(left)
            else:
                clone_args = dict(right)
            if expect:
                assert matchers.MatchNote(**left) == notice.clone(**clone_args)
                assert not matchers.MatchNote(**left) == notice.clone(
                    **{**clone_args, "severity": notices.ErrorSeverity("arg-type")}
                )

            else:
                assert matchers.MatchNote(**left) != notice.clone(**clone_args)
