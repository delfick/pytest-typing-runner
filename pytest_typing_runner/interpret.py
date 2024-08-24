import dataclasses
import enum
import pathlib
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self, assert_never

from . import errors, notice_changers, notices, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvalidMypyOutputLine(errors.PyTestTypingRunnerException):
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


class FileContent:
    regexes: ClassVar[Mapping[str, re.Pattern[str]]] = {
        "potential_instruction": re.compile(r"^\s*#\s*\^"),
        "instruction": re.compile(
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
        ),
        "assignment": re.compile(r"^(?P<var_name>[a-zA-Z0-9_]+)\s*(:[^=]+)?(=|$)"),
        "reveal": re.compile(r"^\s*reveal_type\([^\)]+"),
    }

    class _Instruction(enum.Enum):
        NAME = "NAME"
        REVEAL = "REVEAL"
        ERROR = "ERROR"
        NOTE = "NOTE"

    @classmethod
    def parse(
        cls, content: str, /, *, into: protocols.FileNotices
    ) -> tuple[str, protocols.FileNotices]:
        line_number = 0
        result: list[str] = [""]
        file_notices = into.clear(clear_names=True)
        previous_code_line_number: int

        for line in content.split("\n"):
            line_number += 1
            result.append(line)

            m = cls.regexes["instruction"].match(line)
            if m is None:
                if cls.regexes["potential_instruction"].match(line):
                    raise AssertionError(
                        f"Looks like line is trying to be an expectation but it didn't pass the regex for one: {line}"
                    )

                previous_code_line_number = line_number
                continue

            gd = m.groupdict()
            prefix_whitespace = gd["prefix_whitespace"]
            instruction = cls._Instruction(gd["instruction"])
            error_type = (gd.get("error_type", "") or "").strip()
            name = gd.get("name", "") or ""
            rest = gd["rest"].strip()

            if error_type and instruction is not cls._Instruction.ERROR:
                raise ValueError(
                    f"Only Error instructions should be of the form 'INSTRUCTION(error_type)', got '{line}'"
                )

            if name:
                file_notices = file_notices.set_name(name, previous_code_line_number)

            def modify_line(
                line: int, /, *, change: protocols.LineNoticesChanger
            ) -> protocols.FileNotices:
                return notice_changers.ModifyLine(
                    name_or_line=line, line_must_exist=False, change=change
                )(file_notices)

            if instruction is cls._Instruction.REVEAL:
                previous_line = result[previous_code_line_number].strip()
                if not cls.regexes["reveal"].match(previous_line):
                    m = cls.regexes["assignment"].match(previous_line)
                    if m:
                        result.insert(
                            previous_code_line_number + 1,
                            f"{prefix_whitespace}reveal_type({m.groupdict()['var_name']})",
                        )
                        line_number += 1
                        previous_code_line_number += 1
                        if name:
                            file_notices = file_notices.set_name(name, previous_code_line_number)
                    else:
                        result[previous_code_line_number] = (
                            f"{prefix_whitespace}reveal_type({previous_line})"
                        )

                file_notices = modify_line(
                    previous_code_line_number,
                    change=notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(
                                severity=notices.NoteSeverity(),
                                msg=notices.ProgramNotice.reveal_msg(rest),
                            )
                        ]
                    ),
                )
            elif instruction is cls._Instruction.ERROR:
                assert error_type, "Must use `# ^ ERROR(error-type) ^ error here`"
                file_notices = modify_line(
                    previous_code_line_number,
                    change=notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            line_notices.generate_notice(
                                severity=notices.ErrorSeverity(error_type), msg=rest
                            )
                        ]
                    ),
                )
            elif instruction is cls._Instruction.NOTE:
                file_notices = modify_line(
                    previous_code_line_number,
                    change=notice_changers.ModifyLatestMatch(
                        must_exist=False,
                        matcher=lambda notice: not notice.is_type_reveal,
                        change=lambda notice: notice.clone(
                            severity=notices.NoteSeverity(), msg=f"{notice.msg}\n{rest}"
                        ),
                    ),
                )
            elif instruction is cls._Instruction.NAME:
                assert name, "Must use a `# ^ NAME[tag-name] ^`"
            else:
                assert_never(instruction)

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
    _FCP: protocols.FileNoticesParser = FileContent.parse
