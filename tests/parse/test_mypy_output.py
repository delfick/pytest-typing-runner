import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notices, parse


class TestMypyOutput:
    class TestLineMatch:
        def test_it_complains_if_severity_is_not_note_or_error(self) -> None:
            with pytest.raises(parse.errors.UnknownSeverity) as e:
                parse.MypyOutput._LineMatch.match(
                    'djangoexample/views.py:53: wat: Revealed type is "djangoexample.exampleapp.models.Child2QuerySet"'
                )
            assert e.value.severity == "wat"

        def test_it_does_not_match_an_empty_line(self) -> None:
            m = parse.MypyOutput._LineMatch.match("")
            assert m is None

        def test_it_matches_type_reveals(self) -> None:
            m = parse.MypyOutput._LineMatch.match(
                'djangoexample/views.py:53: note: Revealed type is "djangoexample.exampleapp.models.Child2QuerySet"'
            )
            assert m == parse.MypyOutput._LineMatch(
                filename="djangoexample/views.py",
                line_number=53,
                col=None,
                severity=notices.NoteSeverity(),
                msg='Revealed type is "djangoexample.exampleapp.models.Child2QuerySet"',
            )

        def test_it_matches_notes(self) -> None:
            m = parse.MypyOutput._LineMatch.match(
                "djangoexample/views.py:20: note: Possible overload variants:"
            )
            assert m == parse.MypyOutput._LineMatch(
                filename="djangoexample/views.py",
                line_number=20,
                col=None,
                severity=notices.NoteSeverity(),
                msg="Possible overload variants:",
            )

        def test_it_matches_errors(self) -> None:
            m = parse.MypyOutput._LineMatch.match(
                "djangoexample/views.py:18: error: Missing return statement  [empty-body]"
            )
            assert m == parse.MypyOutput._LineMatch(
                filename="djangoexample/views.py",
                line_number=18,
                col=None,
                severity=notices.ErrorSeverity("empty-body"),
                msg="Missing return statement",
            )

        def test_it_matches_with_column_numbers(self) -> None:
            # Note mypy only shows column numbers with --show-column-numbers
            m = parse.MypyOutput._LineMatch.match(
                'djangoexample/views.py:15:24: error: Unsupported operand types for + ("str" and "int")  [operator]'
            )
            assert m == parse.MypyOutput._LineMatch(
                filename="djangoexample/views.py",
                line_number=15,
                col=24,
                severity=notices.ErrorSeverity("operator"),
                msg='Unsupported operand types for + ("str" and "int")',
            )

        def test_it_does_not_match_on_bad_line(self) -> None:
            m = parse.MypyOutput._LineMatch.match(
                'djangoexample/views.py:15 wat: Unsupported operand types for + ("str" and "int")  [operator]'
            )
            assert m is None

    class TestParse:
        def test_it_complains_if_invalid_lines(self, tmp_path: pathlib.Path) -> None:
            program_notices = notices.ProgramNotices()

            mypy_output = textwrap.dedent("""
            two/three.py:7: note: Revealed type is "ONE"
            mainsfd .py:7: note
            """)

            with pytest.raises(parse.errors.InvalidMypyOutputLine) as e:
                parse.MypyOutput.parse(
                    mypy_output.strip().split("\n"),
                    normalise=lambda notice: notice,
                    into=program_notices,
                    root_dir=tmp_path,
                )

            assert e.value.line == "mainsfd .py:7: note"

        def test_it_can_parse_mypy_output(self, tmp_path: pathlib.Path) -> None:
            program_notices = notices.ProgramNotices()

            mypy_output = textwrap.dedent("""
            main.py:7: note: Revealed type is "ONE"
            main.py:11: note: Revealed type is "TWO"
            main.py:14: error: Cannot resolve keyword 'nup' into field. Choices are: good, id  [misc]
            two/three.py:7: note: Revealed type is "ONE"
            three/four/five.py:2: note: a note
            three/four/five.py:2: error: broken  [misc]
            three/six/five.py:20: error: more broken  [arg-type]
            """)

            parsed = parse.MypyOutput.parse(
                mypy_output.strip().split("\n"),
                normalise=lambda notice: notice,
                into=program_notices,
                root_dir=tmp_path,
            )

            expected_locations = sorted(
                [
                    main_location := tmp_path / "main.py",
                    two_three_location := tmp_path / "two" / "three.py",
                    three_four_five_location := tmp_path / "three" / "four" / "five.py",
                    three_six_five_location := tmp_path / "three" / "six" / "five.py",
                ]
            )
            assert list(parsed.known_locations()) == expected_locations

            expected_main = [
                matchers.MatchNote(
                    location=main_location, line_number=7, msg='Revealed type is "ONE"'
                ),
                matchers.MatchNote(
                    location=main_location, line_number=11, msg='Revealed type is "TWO"'
                ),
                matchers.MatchNotice(
                    location=main_location,
                    line_number=14,
                    severity=notices.ErrorSeverity("misc"),
                    msg="Cannot resolve keyword 'nup' into field. Choices are: good, id",
                ),
            ]
            expected_two_three = [
                matchers.MatchNote(
                    location=two_three_location, line_number=7, msg='Revealed type is "ONE"'
                )
            ]
            expected_three_four_five = [
                matchers.MatchNote(location=three_four_five_location, line_number=2, msg="a note"),
                matchers.MatchNotice(
                    location=three_four_five_location,
                    line_number=2,
                    severity=notices.ErrorSeverity("misc"),
                    msg="broken",
                ),
            ]
            expected_three_six_five = [
                matchers.MatchNotice(
                    location=three_six_five_location,
                    line_number=20,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="more broken",
                ),
            ]

            assert list(parsed.notices_at_location(tmp_path / "main.py") or []) == expected_main
            assert (
                list(parsed.notices_at_location(tmp_path / "two" / "three.py") or [])
                == expected_two_three
            )
            assert (
                list(parsed.notices_at_location(tmp_path / "three" / "four" / "five.py") or [])
                == expected_three_four_five
            )
            assert (
                list(parsed.notices_at_location(tmp_path / "three" / "six" / "five.py") or [])
                == expected_three_six_five
            )

            assert list(parsed) == [
                *expected_main,
                *expected_three_four_five,
                *expected_three_six_five,
                *expected_two_three,
            ]

        def test_it_can_normalise_notices(self, tmp_path: pathlib.Path) -> None:
            program_notices = notices.ProgramNotices()

            mypy_output = textwrap.dedent("""
            main.py:7: note: Revealed type is "ONE"
            main.py:11: note: Revealed type is "TWO"
            main.py:14: error: Cannot resolve keyword 'nup' into field. Choices are: good, id  [misc]
            two/three.py:7: note: Revealed type is "ONE"
            three/four/five.py:2: note: a note
            three/four/five.py:2: error: broken  [misc]
            three/six/five.py:20: error: more broken  [arg-type]
            """)

            parsed = parse.MypyOutput.parse(
                mypy_output.strip().split("\n"),
                normalise=lambda notice: notice.clone(
                    msg=notice.msg.replace("broken", "CLEAN")
                    .replace("Revealed", "REVEAL")
                    .replace("nup", "NUP")
                ),
                into=program_notices,
                root_dir=tmp_path,
            )

            expected_locations = sorted(
                [
                    main_location := tmp_path / "main.py",
                    two_three_location := tmp_path / "two" / "three.py",
                    three_four_five_location := tmp_path / "three" / "four" / "five.py",
                    three_six_five_location := tmp_path / "three" / "six" / "five.py",
                ]
            )
            assert list(parsed.known_locations()) == expected_locations

            expected = [
                matchers.MatchNote(
                    location=main_location, line_number=7, msg='REVEAL type is "ONE"'
                ),
                matchers.MatchNote(
                    location=main_location, line_number=11, msg='REVEAL type is "TWO"'
                ),
                matchers.MatchNotice(
                    location=main_location,
                    line_number=14,
                    severity=notices.ErrorSeverity("misc"),
                    msg="Cannot resolve keyword 'NUP' into field. Choices are: good, id",
                ),
                matchers.MatchNote(location=three_four_five_location, line_number=2, msg="a note"),
                matchers.MatchNotice(
                    location=three_four_five_location,
                    line_number=2,
                    severity=notices.ErrorSeverity("misc"),
                    msg="CLEAN",
                ),
                matchers.MatchNotice(
                    location=three_six_five_location,
                    line_number=20,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="more CLEAN",
                ),
                matchers.MatchNote(
                    location=two_three_location, line_number=7, msg='REVEAL type is "ONE"'
                ),
            ]

            assert list(parsed) == expected
