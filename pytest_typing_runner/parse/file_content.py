import dataclasses
import enum
import functools
import re
from collections.abc import Iterator, MutableSequence, Sequence
from typing import TYPE_CHECKING, ClassVar, cast

from typing_extensions import Self, assert_never

from .. import notice_changers, notices, protocols
from . import errors as parse_errors
from . import protocols as parse_protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineBefore:
    """
    Implementation of :protocol:`pytest_typing_runner.parse.protocols.ParsedLineBefore`
    """

    lines: MutableSequence[str]
    line_number_for_name: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineAfter:
    """
    Implementation of :protocol:`pytest_typing_runner.parse.protocols.ParsedLineAfter`
    """

    names: Sequence[str]
    real_line: bool
    notice_changers: Sequence[protocols.LineNoticesChanger]
    modify_lines: parse_protocols.ModifyParsedLineBefore | None


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommentMatch:
    """
    Represents the information for a single comment containing an expected notice

    Implementation of :protocol:`pytest_typing_runner.parse.protocols.CommentMatch`
    """

    severity: protocols.Severity

    msg: str | protocols.NoticeMsg = ""
    names: Sequence[str] = dataclasses.field(default_factory=tuple)

    is_reveal: bool = False
    is_error: bool = False
    is_note: bool = False
    is_warning: bool = False
    is_whole_line: bool = False

    modify_lines: parse_protocols.ModifyParsedLineBefore | None = None


def _make_msg(
    *, msg: str, msg_maker_name: str, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
) -> str | protocols.NoticeMsg:
    if not msg_maker_name:
        return msg

    if msg_maker_map is None:
        raise parse_errors.InvalidMsgMaker(want=msg_maker_name, available=None)

    msg_maker = msg_maker_map.get(msg_maker_name)

    if msg_maker is None:
        raise parse_errors.InvalidMsgMaker(want=msg_maker_name, available=msg_maker_map.available)

    return msg_maker(pattern=msg)


@dataclasses.dataclass(frozen=True, kw_only=True)
class InlineCommentMatch(CommentMatch):
    r"""
    Represents the information for a single inline mypy stubtest style comment

    Implementation of :protocol:`pytest_typing_runner.parse.protocols.CommentMatch`

    Will match a comment hash followed by a single letter ``N``, ``E`` or ``W``
    indicating ``note``, ``error`` and ``warning`` severity respectively.

    And then either followed by a lonely colon or a colon followed by a column number
    and then the message.

    i.e.

    * ``# N: Revealed type is "builtins.int"``
    * ``# E: Incompatible types in assignment  [assignment]``

    Where further hashes in the message may be escaped with a ``\``
    """

    class _Instruction(enum.Enum):
        N = "N"
        E = "E"
        W = "W"

    instruction_regex: ClassVar[re.Pattern[str]] = re.compile(
        r"(?P<instruction>N|E|W)(<(?P<msg_maker_name>[^>]+)>)?:((?P<col>\d+) )? (?P<rest>.+)"
    )

    error_type_regex: ClassVar[re.Pattern[str]] = re.compile(r"\s+\[(?P<error_type>[^\]]+)\]\s*$")

    # Used to split by unescaped hashes
    split_regex: ClassVar[re.Pattern[str]] = re.compile(r"(?<!\\)# ?")

    @classmethod
    def make_parser(cls) -> parse_protocols.LineParser:
        """
        Yield a parser for parsing a line.

        Wraps :func:`match` with a :class:`InstructionParser`
        """
        return InstructionParser(parser=cls.match).parse

    @classmethod
    def match(
        cls, line: str, /, *, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
    ) -> Iterator[Self]:
        """
        Yield a comment match for lines that match an instruction

        Implementation of :protocol:`pytest_typing_runner.parse.protocols.CommentMatchMaker`

        This will make sure:

        * No match yields no comment matches
        * E instruction may have an optional error type
        * E instructions sets ``is_error=True``
        * N instructions sets ``is_note=True``
        * W instructions sets ``is_warning=True``
        * All instructions set ``is_whole_line=False``

        If the instruction is followed by a string in angle brackets then that
        can be used to specify how the ``msg`` is compared.

        For example: ``# N<regex>: thing.+`` will match against any ``note``
        that begins with "thing" and is followed by one or more characters.

        Lines that only have whitespace before the first hash will be ignored
        """
        if "#" not in line:
            return

        split = list(cls.split_regex.split(line))
        if len(split) < 2:
            return

        if not split[0].strip():
            return

        for part in split:
            m = cls.instruction_regex.match(part)
            if m is None:
                continue

            gd = m.groupdict()
            instruction = cls._Instruction(gd["instruction"])
            rest = gd["rest"].strip()
            error_type = ""

            if instruction is cls._Instruction.E:
                me = cls.error_type_regex.search(rest)
                if me:
                    error_type = me.groupdict()["error_type"]
                    rest = rest[: me.span()[0]]

            msg = _make_msg(
                msg=rest,
                msg_maker_name=(gd["msg_maker_name"] or "").strip(),
                msg_maker_map=msg_maker_map,
            )

            match instruction:
                case cls._Instruction.E:
                    yield cls(
                        names=[],
                        is_error=True,
                        is_whole_line=False,
                        severity=notices.ErrorSeverity(error_type),
                        msg=msg,
                    )
                case cls._Instruction.N:
                    yield cls(
                        names=[],
                        is_note=True,
                        is_whole_line=False,
                        severity=notices.NoteSeverity(),
                        msg=msg,
                    )
                case cls._Instruction.W:
                    yield cls(
                        names=[],
                        is_warning=True,
                        is_whole_line=False,
                        severity=notices.WarningSeverity(),
                        msg=msg,
                    )
                case _:
                    assert_never(instruction)


@dataclasses.dataclass(frozen=True, kw_only=True)
class InstructionMatch(CommentMatch):
    """
    Represents the information for a single instruction comment

    Implementation of :protocol:`pytest_typing_runner.parse.protocols.CommentMatch`

    Will match the form:

    ``# ^ INSTRUCTION(error-type)[name]<match> ^ msg``

    Where INSTRUCTION is one of:

    * NAME
    * REVEAL
    * ERROR
    * NOTE
    * WARNING

    And ``error-type`` is only valid for ``ERROR`` instructions.

    The ``name`` is a way of registered a name for that line.

    And ``match`` says how to compare ``msg`` in this notice to the ``msg``
    in the notice that was received for this file and line.

    The default ``match`` options are ``plain``, ``regex`` and ``glob``.

    The ``REVEAL`` instruction is special in that it will ensure it is preceded
    by a ``reveal_type(...)`` line in the file.
    """

    class _Instruction(enum.Enum):
        NAME = "NAME"
        REVEAL = "REVEAL"
        ERROR = "ERROR"
        NOTE = "NOTE"
        WARNING = "WARNING"

    potential_instruction_regex: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*#\s*(\^|[a-zA-Z]+\s+\^)"
    )

    instruction_regex: ClassVar[re.Pattern[str]] = re.compile(
        # ^ INSTR >>
        r"^(?P<prefix_whitespace>\s*)"
        r"#\s*\^\s*(?P<instruction>NAME|REVEAL|ERROR|WARNING|NOTE)"
        # (error_type)?
        r"("
        r"\((?P<error_type>[^\)]*)\)"
        r")?"
        # [name]?
        r"("
        r"\[(?P<name>[^\]]*)\]"
        r")?"
        # <match>?
        r"("
        r"<(?P<msg_maker_name>[^>]+)>"
        r")?"
        # << ^
        r"\s*\^"
        r"\s*(?P<rest>.*)"
    )
    assignment_regex: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<var_name>[a-zA-Z0-9_]+)\s*(:[^=]+)?(=|$)"
    )
    reveal_regex: ClassVar[re.Pattern[str]] = re.compile(r"^\s*reveal_type\([^\)]+")

    @classmethod
    def _modify_for_reveal(
        cls, *, prefix_whitespace: str, before: _ParsedLineBefore
    ) -> Iterator[str]:
        previous_line = before.lines[before.line_number_for_name].strip()
        if not cls.reveal_regex.match(previous_line):
            m = cls.assignment_regex.match(previous_line)
            if m:
                yield f"{prefix_whitespace}{previous_line}"
                yield f"{prefix_whitespace}reveal_type({m.groupdict()['var_name']})"
            else:
                yield f"{prefix_whitespace}reveal_type({previous_line})"

    @classmethod
    def make_parser(cls) -> parse_protocols.LineParser:
        """
        Yield a parser for parsing a line.

        Wraps :func:`match` with a :class:`InstructionParser`
        """
        return InstructionParser(parser=cls.match).parse

    @classmethod
    def match(
        cls, line: str, /, *, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
    ) -> Iterator[Self]:
        """
        Yield a comment match for lines that match an instruction

        Implementation of :protocol:`pytest_typing_runner.parse.protocols.CommentMatchMaker`

        This will make sure:

        * No match yields no comment matches
        * ERROR instruction must have an error type
        * Only ERROR instructions have an error type
        * NAME instructions must have a name
        * NAME instructions sets none of the ``is_xxx`` properties
        * ERROR instructions sets ``is_error=True``
        * REVEAL instructions sets ``is_reveal=True`` and ``is_note=True``
        * NOTE instructions sets ``is_note=True``
        * WARNING instructions sets ``is_warning=True``
        * All instructions set ``is_whole_line=True``

        When a REVEAL instruction is found it will modify the line such that it is
        preceded by a ``reveal_type(...)`` line.

        * If the line is already a ``reveal_type`` then it is not changed
        * If the line is an assignment, a line is added that does a ``reveal_type`` on the assigned variable
        * Otherwise the line is wrapped in a ``reveal_type(...)`` call at the appropriate level of indentation
        """
        m = cls.instruction_regex.match(line)
        if m is None:
            if cls.potential_instruction_regex.match(line):
                raise parse_errors.InvalidInstruction(
                    reason="Looks like line is trying to be an expectation but it didn't pass the regex for one",
                    line=line,
                )

            return

        gd = m.groupdict()
        prefix_whitespace = gd["prefix_whitespace"]
        instruction = cls._Instruction(gd["instruction"])
        error_type = (gd.get("error_type", "") or "").strip()
        names = [name] if (name := gd.get("name", "") or "") else []
        rest = gd["rest"].strip()

        if instruction is cls._Instruction.REVEAL:
            rest = notices.ProgramNotice.reveal_msg(rest)

        msg = _make_msg(
            msg=rest,
            msg_maker_name=(gd["msg_maker_name"] or "").strip(),
            msg_maker_map=msg_maker_map,
        )

        if error_type and instruction is not cls._Instruction.ERROR:
            raise parse_errors.InvalidInstruction(
                reason="Only Error instructions should be of the form 'INSTRUCTION(error_type)'",
                line=line,
            )

        if instruction is cls._Instruction.ERROR and not error_type:
            raise parse_errors.InvalidInstruction(
                reason="Must use `# ^ ERROR(error-type) ^` with the ERROR instruction",
                line=line,
            )

        if instruction is cls._Instruction.NAME and not name:
            raise parse_errors.InvalidInstruction(
                reason="Must use `# ^ NAME[name] ^` with the NAME instruction",
                line=line,
            )

        match instruction:
            case cls._Instruction.NAME:
                yield cls(names=names, severity=notices.NoteSeverity(), is_whole_line=True)
            case cls._Instruction.REVEAL:
                yield cls(
                    names=names,
                    is_reveal=True,
                    is_note=True,
                    is_whole_line=True,
                    severity=notices.NoteSeverity(),
                    msg=msg,
                    modify_lines=functools.partial(
                        cls._modify_for_reveal, prefix_whitespace=prefix_whitespace
                    ),
                )
            case cls._Instruction.ERROR:
                yield cls(
                    names=names,
                    is_error=True,
                    is_whole_line=True,
                    severity=notices.ErrorSeverity(error_type),
                    msg=msg,
                )
            case cls._Instruction.WARNING:
                yield cls(
                    names=names,
                    is_warning=True,
                    is_whole_line=True,
                    severity=notices.WarningSeverity(),
                    msg=msg,
                )
            case cls._Instruction.NOTE:
                yield cls(
                    names=names,
                    is_note=True,
                    is_whole_line=True,
                    severity=notices.NoteSeverity(),
                    msg=msg,
                )
            case _:
                assert_never(instruction)


@dataclasses.dataclass(frozen=True, kw_only=True)
class InstructionParser:
    """
    Implements a wrapper around
    a :protocol:`pytest_typing_runner.parse.protocols.CommentMatchMaker` parser
    that will create the appropriate notice changers.
    """

    parser: parse_protocols.CommentMatchMaker

    def parse(
        self,
        before: parse_protocols.ParsedLineBefore,
        /,
        msg_maker_map: protocols.NoticeMsgMakerMap | None = None,
    ) -> parse_protocols.ParsedLineAfter:
        """
        Will run the parser over the latest line and determine notice changers
        and whether the line should be considered real.

        * No matches produces a real line with no changes
        * All names on matches get passed along
        * If there are multiple matches with a ``modify_lines`` an error is raised
        * If there is a ``modify_lines`` it is passed along
        * ``is_reveal=True`` results in appending a type reveal to the notices
        * ``is_error=True`` results in appending a notice with the severity and msg
          from the match
        * ``is_note=True`` and ``is_reveal=False`` will result in a note notice
          either being appended to the end of the line, or added to the latest
          notice if that notice is a non reveal note.
        * The line is considered real if none of the matches are for the whole line

        Implementation of :protocol:`pytest_typing_runner.parse.protocols.LineParser`
        """
        line = before.lines[-1]
        matches = list(self.parser(line, msg_maker_map=msg_maker_map))
        if not any(matches):
            return _ParsedLineAfter(
                modify_lines=None, notice_changers=[], names=[], real_line=True
            )

        names: list[str] = []
        changers: list[protocols.LineNoticesChanger] = []
        modify_lines: parse_protocols.ModifyParsedLineBefore | None = None

        def add(match: parse_protocols.CommentMatch) -> None:
            nonlocal modify_lines

            names.extend(match.names)
            if match.modify_lines:
                if modify_lines is not None:
                    raise parse_errors.TooManyModifyLines(line=line)
                modify_lines = match.modify_lines

            if match.is_reveal:
                changers.append(
                    notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(severity=match.severity, msg=match.msg)
                        ]
                    )
                )
            elif match.is_error:
                changers.append(
                    notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(severity=match.severity, msg=match.msg)
                        ]
                    )
                )
            elif match.is_warning:
                changers.append(
                    notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(severity=match.severity, msg=match.msg)
                        ]
                    )
                )
            elif match.is_note and isinstance(match.msg, str):
                skip: bool = False

                def matcher(notice: protocols.ProgramNotice, /) -> bool:
                    nonlocal skip
                    if skip:
                        return False
                    if notice.severity == notices.ErrorSeverity("") or notice.is_type_reveal:
                        skip = True
                        return False
                    if not notice.msg.is_plain:
                        skip = True
                        return False
                    return notice.severity == notices.NoteSeverity()

                changers.append(
                    notice_changers.ModifyLatestMatch(
                        must_exist=False,
                        matcher=matcher,
                        change=lambda notice: notice.clone(
                            severity=match.severity,
                            msg="\n".join(
                                [*(() if not notice.msg.raw else (notice.msg.raw,)), match.msg]
                            ),
                        ),
                    )
                )
            elif match.is_note:
                changers.append(
                    notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(
                                severity=notices.NoteSeverity(), msg=match.msg
                            )
                        ]
                    )
                )

        for match in matches:
            add(match)

        return _ParsedLineAfter(
            real_line=any(not match.is_whole_line for match in matches),
            names=names,
            notice_changers=changers,
            modify_lines=modify_lines,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileContent:
    """
    Used to take some content and return a transformed copy with the notices
    that were extracted.

    :param parsers:
        Optional sequence of :protocol:`pytest_typing_runner.parse.protocols.LineParser`
        objects.

        Defaults to using one parser:
        * :class:`pytest_typing_runner.parse.file_content.InstructionMatch.make_parser`
    :param msg_maker_map: Map of names to specific msg makers
    """

    parsers: Sequence[parse_protocols.LineParser] = dataclasses.field(
        default_factory=lambda: (InstructionMatch.make_parser(), InlineCommentMatch.make_parser())
    )

    msg_maker_map: protocols.NoticeMsgMakerMap = dataclasses.field(
        default_factory=notices.NoticeMsgMakerMap
    )

    def _modify(
        self, *, lines: list[str], modified: list[str], line_number: int, line_number_for_name: int
    ) -> tuple[int, int]:
        if len(modified) > 0:
            lines[line_number_for_name] = modified.pop(0)

        if modified:
            diff = len(modified)
            while modified:
                lines.insert(line_number, modified.pop(0))

            line_number_for_name = line_number - 1 + diff
            line_number += diff

        return line_number, line_number_for_name

    def parse(
        self, content: str, /, *, into: protocols.FileNotices
    ) -> tuple[str, protocols.FileNotices]:
        """
        For each line in the content run the ``parsers`` over the line to
        determine what changes to make and what notices will result from
        running the type checker over this file.

        No files will be modified by this function and the transformed string
        should be written to the file by the user of this function.

        Implementation of :protocol:`pytest_typing_runner.protocols.FileNoticesParser`

        :param content: The content to parse
        :param into: The file notices to add notices to
        :raises parse_errors.InvalidLine:
            By the parsers when they encounter strange input
        :returns:
            A tuple of the transformed content and the changed file notices.
        """
        line_number = 0
        result: list[str] = [""]
        file_notices = into
        line_number_for_name: int = 0

        for line in content.split("\n"):
            line_number += 1
            real_line: bool = True
            result.append(line)

            afters: list[parse_protocols.ParsedLineAfter] = []
            for parser in self.parsers:
                before = _ParsedLineBefore(lines=result, line_number_for_name=line_number_for_name)
                after = parser(before, msg_maker_map=self.msg_maker_map)
                if not after.real_line:
                    real_line = False

                if after.modify_lines:
                    line_number, line_number_for_name = self._modify(
                        lines=result,
                        modified=list(after.modify_lines(before=before)),
                        line_number=line_number,
                        line_number_for_name=line_number_for_name,
                    )

                afters.append(after)

            if real_line:
                line_number_for_name = line_number

            for af in afters:
                for name in af.names:
                    file_notices = file_notices.set_name(name, line_number_for_name)

                for change in af.notice_changers:
                    file_notices = notice_changers.ModifyLine(
                        name_or_line=line_number_for_name, line_must_exist=False, change=change
                    )(file_notices)

        return "\n".join(result[1:]), file_notices


if TYPE_CHECKING:
    _FCP: protocols.FileNoticesParser = cast(FileContent, None).parse
    _PLB: parse_protocols.P_ParsedLineBefore = cast(_ParsedLineBefore, None)
    _PLA: parse_protocols.P_ParsedLineAfter = cast(_ParsedLineAfter, None)
    _IM: parse_protocols.P_CommentMatch = cast(InstructionMatch, None)
    _CM: parse_protocols.P_CommentMatch = cast(CommentMatch, None)
    _IMM: parse_protocols.P_CommentMatchMaker = InstructionMatch.match
    _IP: parse_protocols.P_LineParser = cast(InstructionParser, None).parse
