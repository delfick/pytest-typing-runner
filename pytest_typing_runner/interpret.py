import dataclasses
import enum
import functools
import pathlib
import re
from collections.abc import MutableSequence, Sequence
from typing import TYPE_CHECKING, ClassVar, Protocol, cast

from typing_extensions import Self, assert_never

from . import errors, notice_changers, notices, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidLine(errors.PyTestTypingRunnerException):
    pass


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidInstruction(InvalidLine):
    reason: str
    line: str

    def __str__(self) -> str:
        return f"{self.reason}: {self.line}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidMypyOutputLine(InvalidLine):
    """
    Raised when an invalid line from mypy output is encountered
    """

    line: str

    def __str__(self) -> str:
        return f"Line from mypy output is invalid: {self.line}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class UnknownSeverity(InvalidMypyOutputLine):
    """
    Raised when a severity is encountered that is unknown
    """

    severity: str

    def __str__(self) -> str:
        return f"Unknown severity: {self.severity}"


class ParsedLineBefore(Protocol):
    """
    Represents the lines that came before
    """

    @property
    def lines(self) -> MutableSequence[str]:
        """
        The lines that came before this line including the line being matched
        """

    @property
    def line_number_for_name(self) -> int:
        """
        The line number that represents the line being given a name
        """


class ParsedLineAfter(Protocol):
    """
    The changes to make to a line after all comments have been parsed
    """

    @property
    def names(self) -> Sequence[str]:
        """
        Any names to give to the ``line_number_for_name``
        """

    @property
    def notice_changers(self) -> Sequence[protocols.LineNoticesChanger]:
        """
        Any changers for the notices on the ``line_number_for_name`` line

        These are called after all processing of the line is complete
        """

    @property
    def line_number_for_name_adjustment(self) -> int:
        """
        The amount to adjust the ``line_number_for_name`` line. This is used
        before the next comment parser is used
        """

    @property
    def real_line(self) -> bool:
        """
        Indicates if this is a real line

        When False, the ``line_number_for_name`` will not be progressed after
        the line is fully processed
        """


class LineParser(Protocol):
    """
    Function that takes a line and returns instructions for change to
    the lines or to the notices
    """

    def __call__(self, before: ParsedLineBefore, /) -> ParsedLineAfter: ...


class ModifyParsedLineBefore(Protocol):
    """
    Used to modify the lines that came before the comment match

    Must return the amount to move the ``line_number_for_name``
    """

    def __call__(self, *, before: ParsedLineBefore) -> int: ...


class CommentMatch(Protocol):
    @property
    def names(self) -> Sequence[str]:
        """
        Any names to given the ``line_number_for_name`` after the line is fully
        processed.
        """

    @property
    def is_note(self) -> bool:
        """
        Whether this match adds a note
        """

    @property
    def is_reveal(self) -> bool:
        """
        Whether this match adds a type reveal
        """

    @property
    def is_error(self) -> bool:
        """
        Whether this match adds an error
        """

    @property
    def severity(self) -> protocols.Severity:
        """
        The ``severity`` to use if this match adds a notice
        """

    @property
    def msg(self) -> str:
        """
        The ``msg`` to use if this match adds a notice
        """

    @property
    def modify_lines(self) -> ModifyParsedLineBefore | None:
        """
        Used to modify the lines if changes to the file are required
        """


class CommentMatchMaker(Protocol):
    def __call__(self, line: str, /) -> CommentMatch | None: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineBefore:
    """
    Implementation of ParsedLineBefore
    """

    lines: MutableSequence[str]
    line_number_for_name: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineAfter:
    """
    Implementation of ParsedLineAfter
    """

    names: Sequence[str]
    real_line: bool
    notice_changers: Sequence[protocols.LineNoticesChanger]
    line_number_for_name_adjustment: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class InstructionMatch:
    class _Instruction(enum.Enum):
        NAME = "NAME"
        REVEAL = "REVEAL"
        ERROR = "ERROR"
        NOTE = "NOTE"

    severity: protocols.Severity

    msg: str = ""
    names: Sequence[str] = dataclasses.field(default_factory=tuple)

    is_reveal: bool = False
    is_error: bool = False
    is_note: bool = False

    modify_lines: ModifyParsedLineBefore | None = None

    potential_instruction_regex: ClassVar[re.Pattern[str]] = re.compile(r"^\s*#\s*\^")
    instruction_regex: ClassVar[re.Pattern[str]] = re.compile(
        # ^ INSTR >>
        r"^(?P<prefix_whitespace>\s*)"
        r"#\s*\^\s*(?P<instruction>NAME|REVEAL|ERROR|NOTE)"
        # (error_type)?
        r"("
        r"\((?P<error_type>[^\)]*)\)"
        r")?"
        # [name]?
        r"("
        r"\[(?P<name>[^\]]*)\]"
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
    def _modify_for_reveal(cls, *, prefix_whitespace: str, before: _ParsedLineBefore) -> int:
        previous_line = before.lines[before.line_number_for_name].strip()
        if not cls.reveal_regex.match(previous_line):
            m = cls.assignment_regex.match(previous_line)
            if m:
                before.lines.insert(
                    before.line_number_for_name + 1,
                    f"{prefix_whitespace}reveal_type({m.groupdict()['var_name']})",
                )

                return 1
            else:
                before.lines[before.line_number_for_name] = (
                    f"{prefix_whitespace}reveal_type({previous_line})"
                )

        return 0

    @classmethod
    def match(cls, line: str) -> Self | None:
        m = cls.instruction_regex.match(line)
        if m is None:
            if cls.potential_instruction_regex.match(line):
                raise InvalidInstruction(
                    reason="Looks like line is trying to be an expectation but it didn't pass the regex for one",
                    line=line,
                )

            return None

        gd = m.groupdict()
        prefix_whitespace = gd["prefix_whitespace"]
        instruction = cls._Instruction(gd["instruction"])
        error_type = (gd.get("error_type", "") or "").strip()
        names = [name] if (name := gd.get("name", "") or "") else []
        rest = gd["rest"].strip()

        if error_type and instruction is not cls._Instruction.ERROR:
            raise InvalidInstruction(
                reason="Only Error instructions should be of the form 'INSTRUCTION(error_type)'",
                line=line,
            )

        if instruction is cls._Instruction.ERROR and not error_type:
            raise InvalidInstruction(
                reason="Must use `# ^ ERROR(error-type) ^` with the ERROR instruction",
                line=line,
            )

        if instruction is cls._Instruction.NAME and not name:
            raise InvalidInstruction(
                reason="Must use `# ^ NAME[name] ^` with the NAME instruction",
                line=line,
            )

        match instruction:
            case cls._Instruction.NAME:
                return cls(names=names, severity=notices.NoteSeverity())
            case cls._Instruction.REVEAL:
                return cls(
                    names=names,
                    is_reveal=True,
                    severity=notices.NoteSeverity(),
                    msg=notices.ProgramNotice.reveal_msg(rest),
                    modify_lines=functools.partial(
                        cls._modify_for_reveal, prefix_whitespace=prefix_whitespace
                    ),
                )
            case cls._Instruction.ERROR:
                return cls(
                    names=names,
                    is_error=True,
                    severity=notices.ErrorSeverity(error_type),
                    msg=rest,
                )
            case cls._Instruction.NOTE:
                return cls(
                    names=names,
                    is_note=True,
                    severity=notices.NoteSeverity(),
                    msg=rest,
                )
            case _:
                assert_never(instruction)


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommentParser:
    parser: CommentMatchMaker

    def parse(self, before: ParsedLineBefore, /) -> ParsedLineAfter:
        line = before.lines[-1]
        match = self.parser(line)
        if match is None:
            return _ParsedLineAfter(
                line_number_for_name_adjustment=0, notice_changers=[], names=[], real_line=True
            )

        changer: protocols.LineNoticesChanger | None = None
        line_number_for_name_adjustment = 0

        if match.modify_lines:
            line_number_for_name_adjustment = match.modify_lines(before=before)

        if match.is_reveal:
            changer = notice_changers.AppendToLine(
                notices_maker=lambda line_notices: [
                    line_notices.generate_notice(severity=match.severity, msg=match.msg)
                ]
            )
        elif match.is_error:
            changer = notice_changers.AppendToLine(
                notices_maker=lambda line_notices: [
                    line_notices.generate_notice(severity=match.severity, msg=match.msg)
                ]
            )
        elif match.is_note:
            changer = notice_changers.ModifyLatestMatch(
                must_exist=False,
                matcher=lambda notice: not notice.is_type_reveal,
                change=lambda notice: notice.clone(
                    severity=match.severity, msg=f"{notice.msg}\n{match.msg}"
                ),
            )

        return _ParsedLineAfter(
            real_line=False,
            names=match.names,
            notice_changers=() if changer is None else (changer,),
            line_number_for_name_adjustment=line_number_for_name_adjustment,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileContent:
    parsers: Sequence[LineParser] = dataclasses.field(
        default_factory=lambda: (CommentParser(parser=InstructionMatch.match).parse,)
    )

    def parse(
        self, content: str, /, *, into: protocols.FileNotices
    ) -> tuple[str, protocols.FileNotices]:
        line_number = 0
        result: list[str] = [""]
        file_notices = into.clear(clear_names=True)
        line_number_for_name: int = 0
        remaining = list(content.split("\n"))

        for line in content.split("\n"):
            remaining.pop(0)
            line_number += 1
            real_line: bool = True
            result.append(line)

            afters: list[ParsedLineAfter] = []
            for parser in self.parsers:
                before = _ParsedLineBefore(lines=result, line_number_for_name=line_number_for_name)
                after = parser(before)
                afters.append(after)
                if not after.real_line:
                    real_line = False

                if after.line_number_for_name_adjustment:
                    line_number_for_name += after.line_number_for_name_adjustment
                    line_number += after.line_number_for_name_adjustment

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


class MypyOutput:
    """
    Helper class for parsing output from running Mypy.

    .. code-block:: python

        from pytest_typing_runner import interpret, protocols
        from collections.abc import Sequence
        import pathlib


        empty_program_notices: protocols.ProgramNotices = ...

        # root_dir is going to be the path mypy was run in
        root_dir: pathlib.Path = ...

        # note that mypy output should be only the lines that have notes and errors
        # this means excluding blank lines and things like "Found 6 errors" or
        # messages from the daemon output.
        mypy_output: Sequence[str] = ...


        def normalise(notice: protocols.ProgramNotice, /) -> protocols.ProgramNotice | None:
            # opportunity to do any normalisation
            # for example if a version of a library is a particular version then
            # the message may be different
            # return notice as is if no change is required
            # return None to exclude a notice from the result
            return notice.clone(msg=notice.msg.replace("Type[", "type["))


        full_program_notices = interpret.MypyOutput.parse(
            mypy_output,
            into=empty_program_notices,
            normalise=normalise,
            root_dir=root_dir,
        )
    """

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class _LineMatch:
        filename: str
        line_number: int
        col: int | None
        severity: protocols.Severity
        msg: str

        mypy_output_line_regex: ClassVar[re.Pattern[str]] = re.compile(
            r"^(?P<filename>[^:]+):(?P<line_number>\d+)(:(?P<col>\d+))?: (?P<severity>[^:]+): (?P<msg>.+?)(\s+\[(?P<tag>[^\]]+)\])?$"
        )

        @classmethod
        def match(cls, line: str, /) -> Self | None:
            m = cls.mypy_output_line_regex.match(line.strip())
            if m is None:
                return None

            groups = m.groupdict()
            tag = "" if not groups["tag"] else groups["tag"].strip()
            severity_match = groups["severity"]

            severity: protocols.Severity
            if severity_match == "error":
                severity = notices.ErrorSeverity(tag)
            elif severity_match == "note":
                severity = notices.NoteSeverity()
            else:
                raise UnknownSeverity(line=line, severity=severity_match)

            return cls(
                filename=groups["filename"],
                line_number=int(groups["line_number"]),
                col=None if not (col := groups["col"]) else int(col),
                severity=severity,
                msg=groups["msg"].strip(),
            )

    @classmethod
    def parse(
        cls,
        lines: Sequence[str],
        /,
        *,
        normalise: protocols.ProgramNoticeChanger,
        into: protocols.ProgramNotices,
        root_dir: pathlib.Path,
    ) -> protocols.ProgramNotices:
        """
        Parse lines from mypy and return a copy of the provided program notices
        with the notices from the output.

        :param lines:
            Sequence of strings representing each line from mypy output. This assumes
            only the notes and errors from the output, with everything else including
            new lines already being stripped out.
        :param normalise:
            A :protocol:`pytest_typing_runner.protocols.ProgramNoticeChanger` that
            is used on every notice that is added
        :param into:
            The :protocol:pytest_typing_runner.protocols.ProgramNotices` that the
            notices should be added to
        :param root_dir:
            The base directory that each path is added to to create the
            full location for each notice.
        :raises UnknownSeverity:
            For valid mypy lines with an invalid severity
        :raises InvalidMypyOutputLine:
            For any line that is not a valid mypy line.
        :returns:
            Copy of ``into`` with the notices found in the output.
        """
        program_notices = into

        for line in lines:
            match = cls._LineMatch.match(line)
            if match is None:
                raise InvalidMypyOutputLine(line=line)

            program_notices = notice_changers.ModifyFile(
                location=root_dir / match.filename,
                must_exist=False,
                change=notice_changers.ModifyLine(
                    name_or_line=match.line_number,
                    line_must_exist=False,
                    change=notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            normalise(
                                line_notices.generate_notice(
                                    severity=match.severity, msg=match.msg
                                )
                            )
                        ]
                    ),
                ),
            )(program_notices)

        return program_notices


if TYPE_CHECKING:
    _FCP: protocols.FileNoticesParser = cast(FileContent, None).parse
    _PLB: ParsedLineBefore = cast(_ParsedLineBefore, None)
    _PLA: ParsedLineAfter = cast(_ParsedLineAfter, None)
    _IM: CommentMatch = cast(InstructionMatch, None)
    _IMM: CommentMatchMaker = InstructionMatch.match
    _CP: LineParser = cast(CommentParser, None).parse
