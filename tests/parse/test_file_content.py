import dataclasses
import functools
import pathlib
import re
import textwrap
import types
from collections.abc import Iterator, Sequence
from typing import ClassVar

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notice_changers, notices, parse, protocols


def _without_line_numbers(content: str) -> str:
    line_number = 0
    result: list[str] = []

    for line in textwrap.dedent(content).strip().split("\n"):
        m = re.match(r"^0*(?P<line_number>\d+):( ?(?P<rest>.*))$", line)
        assert m is not None, line
        groups = m.groupdict()
        found_line_number = int(groups["line_number"])
        assert found_line_number == line_number + 1
        line_number += 1
        result.append(groups["rest"])

    return "\n".join(result)


class TestInstructionMatch:
    def test_it_lets_through_non_instruction_lines(self) -> None:
        for code_line in [
            "",
            "class Foo:",
            "one: int = 1",
            "def my_func():",
            "# N: blah",
            "# type-ignore[arg-type]",
            "# stuff and things",
        ]:
            assert list(parse.file_content.InstructionMatch.match(code_line)) == []

    def test_it_complains_about_lines_that_look_like_instructions_but_are_not(self) -> None:
        for invalid in [
            "# ^ asdf",
            "# ERROR ^",
            "# ^ ERROR ^",
            "# ^ note ^",
            "# ^ note ^ asdf",
        ]:
            with pytest.raises(parse.errors.InvalidInstruction):
                list(parse.file_content.InstructionMatch.match(invalid))

    def test_it_knows_about_msg_makers(self) -> None:
        msg_maker_map = notices.NoticeMsgMakerMap(
            makers={"one": notices.RegexMsg.create, "two": notices.GlobMsg.create}
        )

        for instruction in parse.file_content.InstructionMatch._Instruction:
            if instruction is parse.file_content.InstructionMatch._Instruction.NAME:
                continue

            instruction_name = instruction.name
            if instruction is parse.file_content.InstructionMatch._Instruction.ERROR:
                instruction_name = f"{instruction_name}(arg-type)"

            if instruction is parse.file_content.InstructionMatch._Instruction.REVEAL:
                expected = 'Revealed type is "hello"'
            else:
                expected = "hello"

            made = list(
                parse.file_content.InstructionMatch.match(
                    f"# ^ {instruction_name} ^ hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, str)
            assert made[0].msg == expected

            made = list(
                parse.file_content.InstructionMatch.match(
                    f"# ^ {instruction_name}<one> ^ hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, notices.RegexMsg)
            assert made[0].msg == expected

            made = list(
                parse.file_content.InstructionMatch.match(
                    f"# ^ {instruction_name}<two> ^ hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, notices.GlobMsg)
            assert made[0].msg == expected

    def test_it_captures_note_instructions(self) -> None:
        assert list(parse.file_content.InstructionMatch.match("# ^ NOTE ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(),
                msg="hello",
                is_note=True,
                is_whole_line=True,
                names=[],
            )
        ]

        assert list(parse.file_content.InstructionMatch.match("# ^ NOTE[one] ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(),
                msg="hello",
                is_note=True,
                is_whole_line=True,
                names=["one"],
            )
        ]

    def test_it_captures_warning_instructions(self) -> None:
        assert list(parse.file_content.InstructionMatch.match("# ^ WARNING ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.WarningSeverity(),
                msg="hello",
                is_warning=True,
                is_whole_line=True,
                names=[],
            )
        ]

        assert list(parse.file_content.InstructionMatch.match("# ^ WARNING[one] ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.WarningSeverity(),
                msg="hello",
                is_warning=True,
                is_whole_line=True,
                names=["one"],
            )
        ]

    def test_it_captures_reveal_instructions(self) -> None:
        class MatchModifyLines:
            def __init__(self, *, prefix_whitespace: str) -> None:
                self.prefix_whitespace = prefix_whitespace

            def __eq__(self, o: object) -> bool:
                assert isinstance(o, functools.partial)
                assert isinstance(o.func, types.MethodType)
                modify_func = modify_func = parse.file_content.InstructionMatch._modify_for_reveal
                assert isinstance(modify_func, types.MethodType)
                assert o.func.__func__ == modify_func.__func__
                assert o.args == ()
                assert o.keywords == {"prefix_whitespace": self.prefix_whitespace}
                return True

            def __call__(self, *, before: parse.protocols.ParsedLineBefore) -> Iterator[str]:
                raise NotImplementedError()

        assert list(parse.file_content.InstructionMatch.match("# ^ REVEAL ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(),
                msg='Revealed type is "hello"',
                is_note=True,
                is_reveal=True,
                is_whole_line=True,
                names=[],
                modify_lines=MatchModifyLines(prefix_whitespace=""),
            )
        ]

        assert list(parse.file_content.InstructionMatch.match("# ^ REVEAL[two] ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(),
                msg='Revealed type is "hello"',
                is_note=True,
                is_reveal=True,
                is_whole_line=True,
                names=["two"],
                modify_lines=MatchModifyLines(prefix_whitespace=""),
            )
        ]

        assert list(parse.file_content.InstructionMatch.match("    # ^ REVEAL[two] ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(),
                msg='Revealed type is "hello"',
                is_note=True,
                is_reveal=True,
                is_whole_line=True,
                names=["two"],
                modify_lines=MatchModifyLines(prefix_whitespace="    "),
            )
        ]

    def test_it_captures_error_instructions(self) -> None:
        assert list(parse.file_content.InstructionMatch.match("# ^ ERROR(arg-type) ^ hello")) == [
            parse.file_content.InstructionMatch(
                severity=notices.ErrorSeverity("arg-type"),
                msg="hello",
                is_error=True,
                is_whole_line=True,
                names=[],
            )
        ]

        assert list(
            parse.file_content.InstructionMatch.match("# ^ ERROR(assignment)[three] ^ there")
        ) == [
            parse.file_content.InstructionMatch(
                severity=notices.ErrorSeverity("assignment"),
                msg="there",
                is_error=True,
                is_whole_line=True,
                names=["three"],
            )
        ]

    def test_error_instructions_must_have_error_type(self) -> None:
        with pytest.raises(parse.errors.InvalidInstruction) as e:
            list(parse.file_content.InstructionMatch.match("# ^ ERROR ^ hello"))

        assert e.value.reason == "Must use `# ^ ERROR(error-type) ^` with the ERROR instruction"

    def test_it_can_parse_name_instruction(self) -> None:
        assert list(parse.file_content.InstructionMatch.match("# ^ NAME[one] ^")) == [
            parse.file_content.InstructionMatch(
                severity=notices.NoteSeverity(), is_whole_line=True, names=["one"]
            )
        ]

    def test_it_only_let_error_instructions_have_error_tag(self) -> None:
        for invalid in [
            "# ^ NAME(nup)[name] ^",
            "# ^ NOTE(nup)[name] ^",
            "# ^ REVEAL(nup)[name] ^",
        ]:
            with pytest.raises(parse.errors.InvalidInstruction) as e:
                list(parse.file_content.InstructionMatch.match(invalid))
            assert (
                e.value.reason
                == "Only Error instructions should be of the form 'INSTRUCTION(error_type)'"
            )


class TestInlineComment:
    def test_it_lets_through_non_inline_comments(self) -> None:
        for code_line in [
            "",
            "class Foo:",
            "one: int = 1",
            "def my_func():",
            "# ^ NOTE ^ blah",
            "# type-ignore[arg-type]",
            "# stuff and things",
            "# N: no code before the line!",
        ]:
            assert list(parse.file_content.InlineCommentMatch.match(code_line)) == []

    def test_it_knows_about_msg_makers(self) -> None:
        msg_maker_map = notices.NoticeMsgMakerMap(
            makers={"one": notices.RegexMsg.create, "two": notices.GlobMsg.create}
        )

        for instruction in parse.file_content.InlineCommentMatch._Instruction:
            expected = "hello"
            instruction_name = instruction.name

            made = list(
                parse.file_content.InlineCommentMatch.match(
                    f"code # {instruction_name}: hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, str)
            assert made[0].msg == expected

            made = list(
                parse.file_content.InlineCommentMatch.match(
                    f"code # {instruction_name}<one>: hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, notices.RegexMsg)
            assert made[0].msg == expected

            made = list(
                parse.file_content.InlineCommentMatch.match(
                    f"code # {instruction_name}<two>: hello", msg_maker_map=msg_maker_map
                )
            )
            assert isinstance(made[0].msg, notices.GlobMsg)
            assert made[0].msg == expected

    def test_it_captures_note_instructions(self) -> None:
        assert list(parse.file_content.InlineCommentMatch.match("code # N: hello")) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.NoteSeverity(),
                msg="hello",
                is_note=True,
                is_whole_line=False,
                names=[],
            )
        ]

    def test_it_captures_warning_instructions(self) -> None:
        assert list(parse.file_content.InlineCommentMatch.match("code # W: hello")) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.WarningSeverity(),
                msg="hello",
                is_warning=True,
                is_whole_line=False,
                names=[],
            )
        ]

    def test_it_captures_error_instructions(self) -> None:
        assert list(
            parse.file_content.InlineCommentMatch.match(
                "code # E: hello  [arg-type] # E: there [one-space]"
            )
        ) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.ErrorSeverity("arg-type"),
                msg="hello",
                is_error=True,
                is_whole_line=False,
                names=[],
            ),
            parse.file_content.InlineCommentMatch(
                severity=notices.ErrorSeverity("one-space"),
                msg="there",
                is_error=True,
                is_whole_line=False,
                names=[],
            ),
        ]

    def test_allows_errors_without_error_types(self) -> None:
        assert list(parse.file_content.InlineCommentMatch.match("code # E: hello ")) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.ErrorSeverity(""),
                msg="hello",
                is_error=True,
                is_whole_line=False,
                names=[],
            )
        ]

    def test_it_understands_escaped_hashes(self) -> None:
        assert list(
            parse.file_content.InlineCommentMatch.match(
                r"code # N: hello \# ablasdf  [one] # E: there \#stuff  [two]"
            )
        ) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.NoteSeverity(),
                msg=r"hello \# ablasdf  [one]",
                is_note=True,
                is_whole_line=False,
                names=[],
            ),
            parse.file_content.InlineCommentMatch(
                severity=notices.ErrorSeverity("two"),
                msg=r"there \#stuff",
                is_error=True,
                is_whole_line=False,
                names=[],
            ),
        ]

    def test_it_lets_other_instructions_have_error_type(self) -> None:
        assert list(
            parse.file_content.InlineCommentMatch.match(
                "code # N: hello  [one] # W: there  [two] # E: wat[no-space]"
            )
        ) == [
            parse.file_content.InlineCommentMatch(
                severity=notices.NoteSeverity(),
                msg="hello  [one]",
                is_note=True,
                is_whole_line=False,
                names=[],
            ),
            parse.file_content.InlineCommentMatch(
                severity=notices.WarningSeverity(),
                msg="there  [two]",
                is_warning=True,
                is_whole_line=False,
                names=[],
            ),
            parse.file_content.InlineCommentMatch(
                severity=notices.ErrorSeverity(""),
                msg="wat[no-space]",
                is_error=True,
                is_whole_line=False,
                names=[],
            ),
        ]


class TestInstructionParser:
    example_comment_matches: ClassVar[Sequence[object]] = (
        pytest.param(
            parse.file_content.CommentMatch(
                is_note=True, is_reveal=True, is_whole_line=True, severity=notices.NoteSeverity()
            ),
            id="reveal",
        ),
        pytest.param(
            parse.file_content.CommentMatch(
                is_note=True, is_whole_line=True, severity=notices.NoteSeverity()
            ),
            id="note",
        ),
        pytest.param(
            parse.file_content.CommentMatch(
                is_error=True, is_whole_line=True, severity=notices.ErrorSeverity("arg-type")
            ),
            id="error",
        ),
        pytest.param(
            parse.file_content.CommentMatch(
                is_warning=True, is_whole_line=True, severity=notices.WarningSeverity()
            ),
            id="warning",
        ),
        pytest.param(
            parse.file_content.CommentMatch(is_whole_line=True, severity=notices.NoteSeverity()),
            id="name",
        ),
    )

    def test_it_makes_no_modification_if_no_comment_match(self) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            return iter([])

        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        assert after.modify_lines is None
        assert after.notice_changers == []
        assert after.names == []
        assert after.real_line

    @pytest.mark.parametrize("match", example_comment_matches)
    def test_passes_on_modify_lines(self, match: parse.protocols.CommentMatch) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def modify_lines(*, before: parse.protocols.ParsedLineBefore) -> Iterator[str]:
            yield ""

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            assert isinstance(match, parse.file_content.CommentMatch)
            yield dataclasses.replace(match, modify_lines=modify_lines)

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is modify_lines
        assert not after.real_line

    @pytest.mark.parametrize("match", example_comment_matches)
    def test_it_passes_on_names(self, match: parse.protocols.CommentMatch) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            assert isinstance(match, parse.file_content.CommentMatch)
            yield dataclasses.replace(match, names=["one"])

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["one"]
        assert not after.real_line

    def test_it_says_is_real_line_if_not_for_whole_line(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.NoteSeverity(),
                msg=notices.ProgramNotice.reveal_msg("hi"),
                names=["two"],
                is_reveal=True,
                is_note=True,
                is_whole_line=False,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["two"]
        assert after.real_line
        assert len(after.notice_changers) == 1
        assert isinstance(after.notice_changers[0], notice_changers.AppendToLine)

    def test_it_adds_append_changer_for_reveal(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.NoteSeverity(),
                msg=notices.ProgramNotice.reveal_msg("hi"),
                names=["two"],
                is_reveal=True,
                is_note=True,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["two"]
        assert not after.real_line

        assert len(after.notice_changers) == 1
        assert isinstance(after.notice_changers[0], notice_changers.AppendToLine)

        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert list(line_notices) == []

        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNote(
                location=tmp_path, line_number=2, msg=notices.ProgramNotice.reveal_msg("hi")
            )
        ]

    def test_it_appends_if_adding_notice_msg(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.NoteSeverity(),
                msg=notices.RegexMsg.create(pattern=".+"),
                names=["two"],
                is_note=True,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["two"]
        assert not after.real_line
        assert len(after.notice_changers) == 1

        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert list(line_notices) == []
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNote(
                location=tmp_path, line_number=2, msg=notices.RegexMsg.create(pattern=".+")
            )
        ]

        # Existing notes but adding non str
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error1")
        n2 = line_notices.generate_notice(
            severity=notices.NoteSeverity(), msg=notices.RegexMsg.create(pattern="note1")
        )
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            n1,
            n2,
            matchers.MatchNote(
                location=tmp_path, line_number=2, msg=notices.RegexMsg.create(pattern=".+")
            ),
        ]

    def test_it_adds_match_latest_matcher_for_note(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.NoteSeverity(),
                msg="stuff",
                names=["two"],
                is_note=True,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["two"]
        assert not after.real_line
        assert len(after.notice_changers) == 1

        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert list(line_notices) == []
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff")
        ]

        # Existing errors
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error1")
        n2 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error2")
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error1",
            ),
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error2",
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff"),
        ]

        # Existing notes
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error1")
        n2 = line_notices.generate_notice(severity=notices.NoteSeverity(), msg="note1")
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error1",
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="note1\nstuff"),
        ]

        # Existing notes but they aren't plain
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error1")
        n2 = line_notices.generate_notice(
            severity=notices.NoteSeverity(), msg=notices.RegexMsg.create(pattern="note1")
        )
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error1",
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="note1"),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff"),
        ]

        # Existing reveal
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.ErrorSeverity("arg-type"), msg="error1")
        n2 = line_notices.generate_notice(
            severity=notices.NoteSeverity(), msg=notices.ProgramNotice.reveal_msg("hi")
        )
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error1",
            ),
            matchers.MatchNote(
                location=tmp_path, line_number=2, msg=notices.ProgramNotice.reveal_msg("hi")
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff"),
        ]

        # Existing note followed by reveal
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.NoteSeverity(), msg="one")
        n2 = line_notices.generate_notice(
            severity=notices.NoteSeverity(), msg=notices.ProgramNotice.reveal_msg("hi")
        )
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNote(location=tmp_path, line_number=2, msg="one"),
            matchers.MatchNote(
                location=tmp_path, line_number=2, msg=notices.ProgramNotice.reveal_msg("hi")
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff"),
        ]

        # Existing note followed by error
        after = parse.file_content.InstructionParser(parser=parser).parse(before)
        n1 = line_notices.generate_notice(severity=notices.NoteSeverity(), msg="one")
        n2 = line_notices.generate_notice(
            severity=notices.ErrorSeverity("assignment"), msg="error"
        )
        line_notices = notices.LineNotices(location=tmp_path, line_number=2).set_notices(
            [n1, n2], allow_empty=True
        )
        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNote(location=tmp_path, line_number=2, msg="one"),
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("assignment"),
                msg="error",
            ),
            matchers.MatchNote(location=tmp_path, line_number=2, msg="stuff"),
        ]

    def test_it_adds_append_changer_for_error(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.ErrorSeverity("arg-type"),
                msg="error",
                names=["three"],
                is_error=True,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["three"]
        assert not after.real_line

        assert len(after.notice_changers) == 1
        assert isinstance(after.notice_changers[0], notice_changers.AppendToLine)

        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert list(line_notices) == []

        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="error",
            )
        ]

    def test_it_adds_append_changer_for_warning(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.WarningSeverity(),
                msg="warn",
                names=["three"],
                is_warning=True,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert after.names == ["three"]
        assert not after.real_line

        assert len(after.notice_changers) == 1
        assert isinstance(after.notice_changers[0], notice_changers.AppendToLine)

        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert list(line_notices) == []

        assert list(after.notice_changers[0](line_notices) or []) == [
            matchers.MatchNotice(
                location=tmp_path,
                line_number=2,
                severity=notices.WarningSeverity(),
                msg="warn",
            )
        ]

    def test_it_otherwise_adds_not_changers(self, tmp_path: pathlib.Path) -> None:
        before = parse.file_content._ParsedLineBefore(lines=[""], line_number_for_name=0)

        def parser(
            line: str, /, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
        ) -> Iterator[parse.protocols.CommentMatch]:
            yield parse.file_content.CommentMatch(
                severity=notices.NoteSeverity(),
                is_error=False,
                is_note=False,
                is_reveal=False,
                is_whole_line=True,
            )

        after = parse.file_content.InstructionParser(parser=parser).parse(before)

        assert after.modify_lines is None
        assert list(after.names) == []
        assert not after.notice_changers
        assert not after.real_line


class TestFileContentModify:
    def test_it_makes_no_change_if_no_modified(self) -> None:
        file_content = parse.FileContent()

        lines = _without_line_numbers("""
        01: reveal_type(a)
        02: # ^ REVEAL ^ things"
        """).split("\n")
        lines.insert(0, "")

        modified: list[str] = []

        line_number, line_number_for_name = file_content._modify(
            lines=["", *lines], modified=modified, line_number=2, line_number_for_name=1
        )

        expected = _without_line_numbers("""
        01: reveal_type(a)
        02: # ^ REVEAL ^ things"
        """).split("\n")

        assert lines == ["", *expected]
        assert (line_number, line_number_for_name) == (2, 1)

    def test_it_makes_no_change_if_only_changes_one_line(self) -> None:
        file_content = parse.FileContent()

        lines = _without_line_numbers("""
        01: a
        02: # ^ REVEAL ^ things"
        """).split("\n")
        lines.insert(0, "")

        modified = [
            "reveal_type(a)",
        ]

        line_number, line_number_for_name = file_content._modify(
            lines=lines, modified=modified, line_number=2, line_number_for_name=1
        )

        expected = _without_line_numbers("""
        01: reveal_type(a)
        02: # ^ REVEAL ^ things"
        """).split("\n")
        assert lines == ["", *expected]
        assert (line_number, line_number_for_name) == (2, 1)

    def test_it_can_modify_simple(self) -> None:
        file_content = parse.FileContent()

        lines = _without_line_numbers("""
        01: a: int = 1
        02: # ^ REVEAL ^ things"
        """).split("\n")
        lines.insert(0, "")

        modified = [
            "a: int = 1",
            "reveal_type(a)",
        ]

        line_number, line_number_for_name = file_content._modify(
            lines=lines, modified=modified, line_number=2, line_number_for_name=1
        )

        expected = _without_line_numbers("""
        01: a: int = 1
        02: reveal_type(a)
        03: # ^ REVEAL ^ things"
        """).split("\n")
        assert lines == ["", *expected]
        assert (line_number, line_number_for_name) == (3, 2)

    def test_it_can_modify_and_move_previous_lines(self) -> None:
        file_content = parse.FileContent()

        lines = _without_line_numbers("""
        01: c
        02: a: int = 1
        03: # ^ NOTE ^ things
        04: # ^ ERROR(arg-type) ^ other
        05: # ^ REVEAL ^ things
        06: b
        """).split("\n")
        lines.insert(0, "")

        modified = [
            "a: int = 1",
            "reveal_type(a)",
        ]

        line_number, line_number_for_name = file_content._modify(
            lines=lines, modified=modified, line_number=5, line_number_for_name=2
        )

        expected = _without_line_numbers("""
        01: c
        02: a: int = 1
        03: # ^ NOTE ^ things
        04: # ^ ERROR(arg-type) ^ other
        05: reveal_type(a)
        06: # ^ REVEAL ^ things
        07: b
        """).split("\n")

        assert lines == ["", *expected]
        assert (line_number, line_number_for_name) == (6, 5)


class TestFileContent:
    @pytest.fixture
    def parser(self) -> protocols.FileNoticesParser:
        return parse.FileContent().parse

    def test_it_can_parse_empty_file(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = ""

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == []
            assert file_notices.known_names == {}
            assert list(file_notices) == []

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

    def test_it_can_parse_file_with_no_instructions(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: model: type[Leader] = Follow1
        02:
        03: class Thing:
        04:     def __init__(self, model: type[Leader]) -> None:
        05:         self.model = model
        06:
        07: found = Concrete.cast_as_concrete(Thing(model=model).model)
        08:
        09: reveal_type(found)
        10:
        11: if True:
        12:     reveal_type(found)
        13:
        14:     thing = Thing(model=model)
        15:     found = Concrete.cast_as_concrete(thing.model)
        """)

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == []
            assert file_notices.known_names == {}
            assert list(file_notices) == []

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

    def test_it_can_parse_notes(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: model: type[Leader] = Follow1
        02: # ^ NOTE[one] ^ a note
        03: # ^ NOTE[one] ^ more
        04: # ^ NOTE ^ even more
        05: 
        06:
        07: if True:
        08:     reveal_type(found)
        09:     # ^ NOTE ^ hi
        """)

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [1, 8]
            assert file_notices.known_names == {"one": 1}

            notices_at_1 = [
                matchers.MatchNote(location=location, line_number=1, msg="a note\nmore\neven more")
            ]
            notices_at_8 = [matchers.MatchNote(location=location, line_number=8, msg="hi")]

            assert list(file_notices.notices_at_line(1) or []) == notices_at_1
            assert list(file_notices.notices_at_line(8) or []) == notices_at_8
            assert list(file_notices) == [*notices_at_1, *notices_at_8]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

    def test_it_can_parse_errors(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: # ^ ERROR(arg-type) ^ an error
        04: # ^ ERROR(arg-type) ^ more
        05: # ^ ERROR(assignment)<regex> ^ another.+
        06: 
        07:
        08: if True:
        09:     reveal_type(found)
        10:     # ^ ERROR(arg-type)[two] ^ hi
        """)

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [2, 9]
            assert file_notices.known_names == {"two": 9}

            notices_at_2 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=2,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="an error",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=2,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="more",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=2,
                    severity=notices.ErrorSeverity("assignment"),
                    msg=notices.RegexMsg.create(pattern="another.+"),
                ),
            ]
            notices_at_9 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=9,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                )
            ]

            assert list(file_notices.notices_at_line(2) or []) == notices_at_2
            assert list(file_notices.notices_at_line(9) or []) == notices_at_9
            assert list(file_notices) == [*notices_at_2, *notices_at_9]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

    def test_it_can_parse_stacked_reveals(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: # ^ REVEAL[three] ^ one
        04: # ^ REVEAL[three] ^ two
        05: # ^ NOTE ^ three
        06: # ^ ERROR(arg-type) ^ four
        """)

        path = "fle.py"
        location = tmp_path / path

        transformed = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: reveal_type(model)
        04: # ^ REVEAL[three] ^ one
        05: # ^ REVEAL[three] ^ two
        06: # ^ NOTE ^ three
        07: # ^ ERROR(arg-type) ^ four
        """)

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [3]
            assert file_notices.known_names == {"three": 3}
            notices_at_3 = [
                matchers.MatchNote(location=location, line_number=3, msg='Revealed type is "one"'),
                matchers.MatchNote(location=location, line_number=3, msg='Revealed type is "two"'),
                matchers.MatchNote(location=location, line_number=3, msg="three"),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="four",
                ),
            ]
            assert list(file_notices.notices_at_line(3) or []) == notices_at_3
            assert list(file_notices) == [*notices_at_3]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

    def test_it_can_parse_names(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: # ^ NAME[three] ^
        04: 
        05:
        06: if True:
        07:     reveal_type(found)
        08:     # ^ NAME[four] ^
        """)

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == []
            assert file_notices.known_names == {"three": 2, "four": 7}
            assert list(file_notices) == []

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

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
        13: # ^ REVEAL[three]<glob> ^ Union[type[simple.models.*], type[simple.models.*]]
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
        15: # ^ REVEAL[three]<glob> ^ Union[type[simple.models.*], type[simple.models.*]]
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
                    msg=notices.GlobMsg.create(
                        pattern=notices.ProgramNotice.reveal_msg(
                            "Union[type[simple.models.*], type[simple.models.*]]"
                        )
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
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

    def test_it_can_parse_everything(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: # ^ REVEAL[one] ^ wat
        04: # ^ ERROR(arg-type) ^ an error
        05: # ^ ERROR(arg-type) ^ more
        06: # ^ ERROR(assignment) ^ another
        07: 
        08: a: int = "asdf"
        09: # ^ ERROR(assignment) ^ other
        10: # ^ REVEAL ^ stuff
        11: # ^ NOTE ^ one
        12: # ^ NOTE ^ two
        13: # ^ NOTE ^ three
        14: # ^ ERROR(assignment) ^ another
        15: # ^ NOTE ^ four
        16:
        17: def other() -> None:
        18:     return 1
        19:     # ^ ERROR(var-annotated) ^ asdf
        20:     # ^ NAME[hi] ^
        21:
        22: if True:
        23:     reveal_type(found)
        24:     # ^ ERROR(arg-type)[other] ^ hi
        25:     # ^ REVEAL[other] ^ asdf
        26:     # ^ REVEAL ^ asdf2
        27:     # ^ ERROR(arg-type)[other] ^ hi
        """)

        path = "fle.py"
        location = tmp_path / path

        transformed = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1
        03: reveal_type(model)
        04: # ^ REVEAL[one] ^ wat
        05: # ^ ERROR(arg-type) ^ an error
        06: # ^ ERROR(arg-type) ^ more
        07: # ^ ERROR(assignment) ^ another
        08: 
        09: a: int = "asdf"
        10: # ^ ERROR(assignment) ^ other
        11: reveal_type(a)
        12: # ^ REVEAL ^ stuff
        13: # ^ NOTE ^ one
        14: # ^ NOTE ^ two
        15: # ^ NOTE ^ three
        16: # ^ ERROR(assignment) ^ another
        17: # ^ NOTE ^ four
        18:
        19: def other() -> None:
        20:     return 1
        21:     # ^ ERROR(var-annotated) ^ asdf
        22:     # ^ NAME[hi] ^
        23:
        24: if True:
        25:     reveal_type(found)
        26:     # ^ ERROR(arg-type)[other] ^ hi
        27:     # ^ REVEAL[other] ^ asdf
        28:     # ^ REVEAL ^ asdf2
        29:     # ^ ERROR(arg-type)[other] ^ hi
        """)

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [3, 9, 11, 20, 25]
            assert file_notices.known_names == {"one": 3, "hi": 20, "other": 25}

            notices_at_3 = [
                matchers.MatchNote(location=location, line_number=3, msg='Revealed type is "wat"'),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="an error",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="more",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
            ]
            notices_at_9 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=9,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="other",
                )
            ]
            notices_at_11 = [
                matchers.MatchNote(
                    location=location, line_number=11, msg='Revealed type is "stuff"'
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=11,
                    msg="one\ntwo\nthree",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=11,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=11,
                    msg="four",
                ),
            ]
            notices_at_20 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=20,
                    severity=notices.ErrorSeverity("var-annotated"),
                    msg="asdf",
                ),
            ]
            notices_at_25 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=25,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
                matchers.MatchNote(
                    location=location, line_number=25, msg='Revealed type is "asdf"'
                ),
                matchers.MatchNote(
                    location=location, line_number=25, msg='Revealed type is "asdf2"'
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=25,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
            ]

            assert list(file_notices.notices_at_line(3) or []) == notices_at_3
            assert list(file_notices.notices_at_line(9) or []) == notices_at_9
            assert list(file_notices.notices_at_line(11) or []) == notices_at_11
            assert list(file_notices.notices_at_line(20) or []) == notices_at_20
            assert list(file_notices.notices_at_line(25) or []) == notices_at_25
            assert list(file_notices) == [
                *notices_at_3,
                *notices_at_9,
                *notices_at_11,
                *notices_at_20,
                *notices_at_25,
            ]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

    def test_it_can_parse_inline_comments(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers("""
        01: a: int = 1
        02: model: type[Leader] = Follow1 
        03: reveal_type(model) # N: Revealed type is "one" # E: an error  [arg-type] # E<regex>: more.*  [arg-type] # E: another  [assignment]
        04: 
        05: a: int = "asdf" # E: other  [assignment]
        06: reveal_type(a) # N: Revealed type is "stuff" # N: one # N: two # N: three # E: another  [assignment] # N: four
        07:
        08: def other() -> None:
        09:     return 1 # E: asdf  [var-annotated]
        10:
        11: if True:
        12:     reveal_type(found) # E: hi  [arg-type] # N: Revealed type is "asdf" # N: Revealed type is "asdf2" # E: hi  [arg-type]
        """)

        path = "fle.py"
        location = tmp_path / path

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [3, 5, 6, 9, 12]
            assert file_notices.known_names == {}

            notices_at_3 = [
                matchers.MatchNote(location=location, line_number=3, msg='Revealed type is "one"'),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="an error",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg=notices.RegexMsg.create(pattern="more.*"),
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
            ]
            notices_at_5 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=5,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="other",
                )
            ]
            notices_at_6 = [
                matchers.MatchNote(
                    location=location, line_number=6, msg='Revealed type is "stuff"'
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=6,
                    msg="one\ntwo\nthree",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=6,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=6,
                    msg="four",
                ),
            ]
            notices_at_9 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=9,
                    severity=notices.ErrorSeverity("var-annotated"),
                    msg="asdf",
                ),
            ]
            notices_at_12 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=12,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
                matchers.MatchNote(
                    location=location, line_number=12, msg='Revealed type is "asdf"'
                ),
                matchers.MatchNote(
                    location=location, line_number=12, msg='Revealed type is "asdf2"'
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=12,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
            ]

            assert list(file_notices.notices_at_line(3) or []) == notices_at_3
            assert list(file_notices.notices_at_line(5) or []) == notices_at_5
            assert list(file_notices.notices_at_line(6) or []) == notices_at_6
            assert list(file_notices.notices_at_line(9) or []) == notices_at_9
            assert list(file_notices.notices_at_line(12) or []) == notices_at_12
            assert list(file_notices) == [
                *notices_at_3,
                *notices_at_5,
                *notices_at_6,
                *notices_at_9,
                *notices_at_12,
            ]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == original
        assertExpected(parsed)

    def test_it_can_parse_inline_comments_combined_with_instruction_comments(
        self, tmp_path: pathlib.Path, parser: protocols.FileNoticesParser
    ) -> None:
        original = _without_line_numbers(r"""
        01: a: int = 1
        02: model: type[Leader] = Follow1 
        03: reveal_type(model) # N: Revealed type is "one" # E: an error  [arg-type] # E: more  [arg-type] # E: another  [assignment]
        04: 
        05: a: int = "asdf" # E: other  [assignment]
        06: reveal_type(a) # N: Revealed type is "stuff" # N: one # N: two # N: three # E: another  [assignment] # N: four
        07:
        08: def other() -> None:
        09:     a: int = str # E: nope  [assignment]
        10:     # ^ REVEAL[a]<regex> ^ builtins\.i.+
        11:     return 1 # E: asdf  [var-annotated]
        12:
        13: if True:
        14:     reveal_type(found) # E: hi  [arg-type] # N<glob>: Revealed type is "asdf" # N: Revealed type is "asdf2" # E: hi  [arg-type]
        15:     # ^ NOTE ^ amaze
        """)

        path = "fle.py"
        location = tmp_path / path

        transformed = _without_line_numbers(r"""
        01: a: int = 1
        02: model: type[Leader] = Follow1 
        03: reveal_type(model) # N: Revealed type is "one" # E: an error  [arg-type] # E: more  [arg-type] # E: another  [assignment]
        04: 
        05: a: int = "asdf" # E: other  [assignment]
        06: reveal_type(a) # N: Revealed type is "stuff" # N: one # N: two # N: three # E: another  [assignment] # N: four
        07:
        08: def other() -> None:
        09:     a: int = str # E: nope  [assignment]
        10:     reveal_type(a)
        11:     # ^ REVEAL[a]<regex> ^ builtins\.i.+
        12:     return 1 # E: asdf  [var-annotated]
        13:
        14: if True:
        15:     reveal_type(found) # E: hi  [arg-type] # N<glob>: Revealed type is "asdf" # N: Revealed type is "asdf2" # E: hi  [arg-type]
        16:     # ^ NOTE ^ amaze
        """)

        def assertExpected(file_notices: protocols.FileNotices) -> None:
            assert list(file_notices.known_line_numbers()) == [3, 5, 6, 9, 10, 12, 15]
            assert file_notices.known_names == {"a": 10}

            notices_at_3 = [
                matchers.MatchNote(location=location, line_number=3, msg='Revealed type is "one"'),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="an error",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="more",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=3,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
            ]
            notices_at_5 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=5,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="other",
                )
            ]
            notices_at_6 = [
                matchers.MatchNote(
                    location=location, line_number=6, msg='Revealed type is "stuff"'
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=6,
                    msg="one\ntwo\nthree",
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=6,
                    severity=notices.ErrorSeverity("assignment"),
                    msg="another",
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=6,
                    msg="four",
                ),
            ]
            notices_at_9 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=9,
                    msg="nope",
                    severity=notices.ErrorSeverity("assignment"),
                ),
            ]
            notices_at_10 = [
                matchers.MatchNote(
                    location=location,
                    line_number=10,
                    msg=notices.RegexMsg.create(
                        pattern=notices.ProgramNotice.reveal_msg(r"builtins\.i.+")
                    ),
                ),
            ]
            notices_at_12 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=12,
                    severity=notices.ErrorSeverity("var-annotated"),
                    msg="asdf",
                ),
            ]
            notices_at_15 = [
                matchers.MatchNotice(
                    location=location,
                    line_number=15,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
                matchers.MatchNote(
                    location=location,
                    line_number=15,
                    msg=notices.GlobMsg.create(pattern='Revealed type is "asdf"'),
                ),
                matchers.MatchNote(
                    location=location, line_number=15, msg='Revealed type is "asdf2"'
                ),
                matchers.MatchNotice(
                    location=location,
                    line_number=15,
                    severity=notices.ErrorSeverity("arg-type"),
                    msg="hi",
                ),
                matchers.MatchNote(location=location, line_number=15, msg="amaze"),
            ]

            assert list(file_notices.notices_at_line(3) or []) == notices_at_3
            assert list(file_notices.notices_at_line(5) or []) == notices_at_5
            assert list(file_notices.notices_at_line(6) or []) == notices_at_6
            assert list(file_notices.notices_at_line(9) or []) == notices_at_9
            assert list(file_notices.notices_at_line(10) or []) == notices_at_10
            assert list(file_notices.notices_at_line(12) or []) == notices_at_12
            assert list(file_notices.notices_at_line(15) or []) == notices_at_15
            assert list(file_notices) == [
                *notices_at_3,
                *notices_at_5,
                *notices_at_6,
                *notices_at_9,
                *notices_at_10,
                *notices_at_12,
                *notices_at_15,
            ]

        replaced, parsed = parser(original, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)

        # And can run again with no further changes
        replaced, parsed = parser(replaced, into=notices.FileNotices(location=location))
        assert replaced == transformed
        assertExpected(parsed)
