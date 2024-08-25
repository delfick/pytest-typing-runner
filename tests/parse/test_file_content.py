import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notices, parse, protocols


def _without_line_numbers(content: str) -> str:
    return "\n".join(line[4:] for line in textwrap.dedent(content).strip().split("\n"))


class TestInstructionMatch:
    @pytest.fixture
    def instruction_parser(self) -> parse.protocols.LineParser:
        return parse.file_content.InstructionMatch.make_parser()

    @pytest.fixture
    def parser(
        self, instruction_parser: parse.protocols.LineParser
    ) -> protocols.FileNoticesParser:
        return parse.FileContent(parsers=(instruction_parser,)).parse

    def test_it_can_parse_whole_file_with_reveals_that_change_the_file(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01:
        02: model: type[Leader] = Follow1
        03: # ^ REVEAL[one] ^ type[leader.models.Leader]
        04:
        05: class Thing:
        06:     def __init__(self, model: type[Leader]) -> None:
        07:         self.model = model
        08:
        09: found = Concrete.cast_as_concrete(Thing(model=model).model)
        10: # ^ REVEAL[two] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        11:
        12: reveal_type(found)
        13: # ^ REVEAL[three] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        14:
        15: if True:
        16:     reveal_type(found)
        17:     # ^ REVEAL[four] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        18:
        19:     thing = Thing(model=model)
        20:     found = Concrete.cast_as_concrete(thing.model)
        21:     # ^ REVEAL[five] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        """)

        path = "fle.py"
        location = tmp_path / path

        transformed = _without_line_numbers("""
        01:
        02: model: type[Leader] = Follow1
        03: reveal_type(model)
        04: # ^ REVEAL[one] ^ type[leader.models.Leader]
        05:
        06: class Thing:
        07:     def __init__(self, model: type[Leader]) -> None:
        08:         self.model = model
        09:
        10: found = Concrete.cast_as_concrete(Thing(model=model).model)
        11: reveal_type(found)
        12: # ^ REVEAL[two] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        13:
        14: reveal_type(found)
        15: # ^ REVEAL[three] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        16:
        17: if True:
        18:     reveal_type(found)
        19:     # ^ REVEAL[four] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        20:
        21:     thing = Thing(model=model)
        22:     found = Concrete.cast_as_concrete(thing.model)
        23:     reveal_type(found)
        24:     # ^ REVEAL[five] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        """)

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [3, 11, 14, 18, 23]
            assert file_notices.known_names == {
                "one": 3,
                "two": 11,
                "three": 14,
                "four": 18,
                "five": 23,
            }

            notices_at_3 = [
                matchers.MatchNote(
                    location=location,
                    line_number=3,
                    msg=notices.ProgramNotice.reveal_msg("type[leader.models.Leader]"),
                )
            ]
            notices_at_11 = [
                matchers.MatchNote(
                    location=location,
                    line_number=11,
                    msg=notices.ProgramNotice.reveal_msg(
                        "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                    ),
                )
            ]
            notices_at_14 = [
                matchers.MatchNote(
                    location=location,
                    line_number=14,
                    msg=notices.ProgramNotice.reveal_msg(
                        "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                    ),
                )
            ]
            notices_at_18 = [
                matchers.MatchNote(
                    location=location,
                    line_number=18,
                    msg=notices.ProgramNotice.reveal_msg(
                        "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                    ),
                )
            ]
            notices_at_23 = [
                matchers.MatchNote(
                    location=location,
                    line_number=23,
                    msg=notices.ProgramNotice.reveal_msg(
                        "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                    ),
                )
            ]

            assert list(file_notices.notices_at_line(3) or []) == notices_at_3
            assert list(file_notices.notices_at_line(11) or []) == notices_at_11
            assert list(file_notices.notices_at_line(14) or []) == notices_at_14
            assert list(file_notices.notices_at_line(18) or []) == notices_at_18
            assert list(file_notices.notices_at_line(23) or []) == notices_at_23

            assert list(file_notices) == [
                *notices_at_3,
                *notices_at_11,
                *notices_at_14,
                *notices_at_18,
                *notices_at_23,
            ]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=parsed)
        assert replaced == transformed
        assertExpected(parsed)
