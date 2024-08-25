import dataclasses
import enum
import functools
import re
from collections.abc import MutableSequence, Sequence
from typing import TYPE_CHECKING, ClassVar, cast

from typing_extensions import Self, assert_never

from .. import notice_changers, notices, protocols
from . import errors as interpret_errors
from . import protocols as interpret_protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineBefore:
    """
    Implementation of :protocol:`pytest_typing_runner.interpert.protocols.ParsedLineBefore`
    """

    lines: MutableSequence[str]
    line_number_for_name: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class _ParsedLineAfter:
    """
    Implementation of :protocol:`pytest_typing_runner.interpert.protocols.ParsedLineAfter`
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

    modify_lines: interpret_protocols.ModifyParsedLineBefore | None = None

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
                raise interpret_errors.InvalidInstruction(
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
            raise interpret_errors.InvalidInstruction(
                reason="Only Error instructions should be of the form 'INSTRUCTION(error_type)'",
                line=line,
            )

        if instruction is cls._Instruction.ERROR and not error_type:
            raise interpret_errors.InvalidInstruction(
                reason="Must use `# ^ ERROR(error-type) ^` with the ERROR instruction",
                line=line,
            )

        if instruction is cls._Instruction.NAME and not name:
            raise interpret_errors.InvalidInstruction(
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
class InstructionParser:
    parser: interpret_protocols.CommentMatchMaker

    def parse(
        self, before: interpret_protocols.ParsedLineBefore, /
    ) -> interpret_protocols.ParsedLineAfter:
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
    parsers: Sequence[interpret_protocols.LineParser] = dataclasses.field(
        default_factory=lambda: (InstructionParser(parser=InstructionMatch.match).parse,)
    )

    def parse(
        self, content: str, /, *, into: protocols.FileNotices
    ) -> tuple[str, protocols.FileNotices]:
        line_number = 0
        result: list[str] = [""]
        file_notices = into.clear(clear_names=True)
        line_number_for_name: int = 0

        for line in content.split("\n"):
            line_number += 1
            real_line: bool = True
            result.append(line)

            afters: list[interpret_protocols.ParsedLineAfter] = []
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


if TYPE_CHECKING:
    _FCP: protocols.FileNoticesParser = cast(FileContent, None).parse
    _PLB: interpret_protocols.P_ParsedLineBefore = cast(_ParsedLineBefore, None)
    _PLA: interpret_protocols.P_ParsedLineAfter = cast(_ParsedLineAfter, None)
    _IM: interpret_protocols.P_CommentMatch = cast(InstructionMatch, None)
    _IMM: interpret_protocols.P_CommentMatchMaker = InstructionMatch.match
    _IP: interpret_protocols.P_LineParser = cast(InstructionParser, None).parse
