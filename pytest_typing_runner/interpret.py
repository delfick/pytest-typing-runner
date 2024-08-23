import dataclasses
import enum
import importlib
import re
import textwrap
from collections.abc import Sequence

from typing_extensions import assert_never

from . import notice_changers, notices, protocols

regexes = {
    "mypy_output_line": re.compile(
        r"^(?P<filename>[^:]+):(?P<line_number>\d+)(:(?P<col>\d+))?: (?P<severity>[^:]+): (?P<msg>.+?)(\s+\[(?P<tag>[^\]]+)\])?$"
    ),
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


@dataclasses.dataclass(frozen=True, kw_only=True)
class _MypyOutputLineMatch:
    filename: str
    line_number: int
    col: int | None
    severity: str
    msg: str
    tag: str


class _Instruction(enum.Enum):
    NAME = "NAME"
    REVEAL = "REVEAL"
    ERROR = "ERROR"
    NOTE = "NOTE"


def parse_notices_from_file(file_notices: protocols.FileNotices, /) -> protocols.FileNotices:
    location = file_notices.location
    if not location.exists() or not (content := textwrap.dedent(location.read_text())):
        return file_notices

    line_number = 0
    result: list[str] = [""]
    previous_code_line_number: int

    for line in content.split("\n"):
        line_number += 1
        result.append(line)

        m = regexes["instruction"].match(line)
        if m is None:
            if regexes["potential_instruction"].match(line):
                raise AssertionError(
                    f"Looks like line is trying to be an expectation but it didn't pass the regex for one: {line}"
                )

            previous_code_line_number = line_number
            continue

        gd = m.groupdict()
        prefix_whitespace = gd["prefix_whitespace"]
        instruction = _Instruction(gd["instruction"])
        error_type = (gd.get("error_type", "") or "").strip()
        name = gd.get("name", "") or ""
        rest = gd["rest"].strip()

        if error_type and instruction is not _Instruction.ERROR:
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

        if instruction is _Instruction.REVEAL:
            previous_line = result[previous_code_line_number].strip()
            if not regexes["reveal"].match(previous_line):
                m = regexes["assignment"].match(previous_line)
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
        elif instruction is _Instruction.ERROR:
            assert error_type, "Must use `# ^ ERROR(error-type) ^ error here`"
            file_notices = modify_line(
                previous_code_line_number,
                change=notice_changers.AppendToLine(
                    notices_maker=lambda line_notices: [
                        line_notices.generate_notice(
                            severity=notices.ErrorSeverity(error_type=error_type), msg=rest
                        )
                    ]
                ),
            )
        elif instruction is _Instruction.NOTE:
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
        elif instruction is _Instruction.NAME:
            assert name, "Must use a `# ^ NAME[tag-name] ^`"
        else:
            assert_never(instruction)

    location.write_text("\n".join(result[1:]))
    return file_notices


def normalise_mypy_msg(msg: str) -> str:
    msg = "\n".join(line for line in msg.split("\n") if not line.startswith(":debug:"))

    if importlib.metadata.version("mypy") == "1.4.0":
        return (
            msg.replace("type[", "Type[")
            .replace("django.db.models.query.QuerySet", "django.db.models.query._QuerySet")
            .replace("Type[Concrete?", "type[Concrete?")
        )
    else:
        return msg


def interpret_mypy_output(
    scenario: protocols.T_Scenario,
    options: protocols.RunOptions[protocols.T_Scenario],
    lines: Sequence[str],
    program_notices: protocols.ProgramNotices | None = None,
) -> protocols.ProgramNotices:
    if program_notices is None:
        program_notices = notices.ProgramNotices()

    matches: list[_MypyOutputLineMatch] = []

    for line in lines:
        m = regexes["mypy_output_line"].match(line.strip())
        if m is None:
            raise ValueError(f"Expected mypy output to be valid, got '{line}'")

        groups = m.groupdict()
        matches.append(
            _MypyOutputLineMatch(
                filename=groups["filename"],
                line_number=int(groups["line_number"]),
                col=None if not (col := groups["col"]) else int(col),
                severity=groups["severity"],
                msg=normalise_mypy_msg(groups["msg"]).strip(),
                tag="" if not groups["tag"] else groups["tag"].strip(),
            )
        )

    for match in matches:
        location = options.cwd / match.filename

        severity: protocols.Severity
        if match.severity == "error":
            severity = notices.ErrorSeverity(error_type=match.tag)
        elif match.severity == "note":
            severity = notices.NoteSeverity()
        else:
            raise ValueError(f"Unknown severity: {match.severity}")

        program_notices = notice_changers.ModifyFile(
            location=location,
            must_exist=False,
            change=notice_changers.ModifyLine(
                name_or_line=match.line_number,
                line_must_exist=False,
                change=notice_changers.AppendToLine(
                    notices_maker=lambda line_notices: [
                        line_notices.generate_notice(severity=severity, msg=match.msg)
                    ]
                ),
            ),
        )(program_notices)

    return program_notices
