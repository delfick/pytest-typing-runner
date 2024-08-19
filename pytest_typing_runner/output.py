import dataclasses
import importlib
import itertools
import pathlib
import re
from collections.abc import Sequence

from . import expectations, protocols

regexes = {
    "mypy_output_line": re.compile(
        r"^(?P<filename>[^:]+):(?P<line_number>\d+)(:(?P<col>\d+))?: (?P<severity>[^:]+): (?P<msg>.+?)(\s+\[(?P<tag>[^\]]+)\])?$"
    )
}


@dataclasses.dataclass(frozen=True, kw_only=True)
class RegexMatch:
    filename: str
    line_number: int
    col: int | None
    severity: str
    msg: str
    tag: str | None


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
) -> protocols.ProgramNotices:
    notices: dict[pathlib.Path, protocols.FileNotices] = {}

    matches: list[RegexMatch] = []

    for line in lines:
        m = regexes["mypy_output_line"].match(line.strip())
        if m is None:
            raise ValueError(f"Expected mypy output to be valid, got '{line}'")

        groups = m.groupdict()
        matches.append(
            RegexMatch(
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
        if location not in notices:
            notices[location] = expectations.FileNotices(location=location)

        if match.severity == "error":
            notices[location] = notices[location].add_error(
                name_or_line=match.line_number, error_type=match.tag or "", error=match.msg
            )
        elif match.severity == "note":
            notices[location] = notices[location].add_note(
                name_or_line=match.line_number, note=match.msg
            )
        else:
            raise ValueError(f"Unknown severity: {match.severity}")

    return expectations.ProgramNotices(notices=notices)


def compare_notices(diff: protocols.DiffNotices) -> None:
    tick = "✓"
    cross = "✘"

    msg: list[str] = []
    different: bool = False

    for path, fdiff in diff:
        msg.append(f"> {path}")
        for line_number, left_notices, right_notices in fdiff:
            for_line: list[str | tuple[str, str]] = []

            for left, right in itertools.zip_longest(left_notices, right_notices):
                if left is None or right is None:
                    for_line.append(
                        (
                            "<NONE>" if left is None else left.display(),
                            "<NONE>" if right is None else right.display(),
                        )
                    )
                    continue

                if right.matches(left):
                    for_line.append(left.display())
                else:
                    for_line.append((left.display(), right.display()))

            prefix = "  | "
            line_check = tick if all(isinstance(m, str) for m in for_line) else cross
            if line_check == cross:
                different = True

            if len(for_line) == 1 and isinstance(for_line[0], str):
                msg.append(f"{prefix}{line_check} {line_number}:")
                msg[-1] = f"{msg[-1]} {for_line[0]}"
            else:
                msg.append(f"{prefix}{line_check} {line_number}:")
                for same_or_different in for_line:
                    if isinstance(same_or_different, str):
                        msg.append(f"{prefix}{tick} {same_or_different}")
                    else:
                        msg.append(f"{prefix}{cross} !! GOT  !! {same_or_different[0]}")
                        msg.append(f"{prefix}  !! WANT !! {same_or_different[1]}")

    if different:
        raise AssertionError("\n" + "\n".join(msg))
