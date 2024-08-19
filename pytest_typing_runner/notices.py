import dataclasses
import enum
import re
import textwrap
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from typing_extensions import assert_never

from . import protocols

regexes = {
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


def parse_notices_from_file(notices: protocols.FileNotices) -> protocols.FileNotices:
    location = notices.location
    if not location.exists() or not (content := textwrap.dedent(location.read_text())):
        return notices

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
            notices = notices.set_name(name, previous_code_line_number)

        for_previous = notices.notices_for_line_number(previous_code_line_number)

        previous: protocols.ProgramNotice | None = None
        if for_previous and for_previous.has_notices:
            previous = list(for_previous)[-1]

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
                        notices = notices.set_name(name, previous_code_line_number)
                else:
                    result[previous_code_line_number] = (
                        f"{prefix_whitespace}reveal_type({previous_line})"
                    )

            notices = notices.add_reveal(name_or_line=previous_code_line_number, revealed=rest)
        elif instruction is _Instruction.ERROR:
            assert error_type, "Must use `# ^ ERROR(error-type) ^ error here`"
            notices = notices.add_error(
                name_or_line=previous_code_line_number, error_type=error_type, error=rest
            )
        elif instruction is _Instruction.NOTE:
            if previous and previous.severity == "note":
                assert for_previous is not None
                clone = previous.clone(msg=f"{previous.msg}\n{rest}")
                notices = notices.set_line_notices(
                    previous_code_line_number,
                    for_previous.replace(
                        lambda original: original.matches(previous),
                        replaced=clone,
                    ),
                )
                previous = clone
            else:
                notices = notices.add_note(name_or_line=previous_code_line_number, note=rest)
        elif instruction is _Instruction.NAME:
            assert name, "Must use a `# ^ NAME[tag-name] ^`"
        else:
            assert_never(instruction)

    location.write_text("\n".join(result[1:]))
    return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class RevealedType:
    name: str
    revealed: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        if self.append:
            return notices.add_reveal(name_or_line=self.name, revealed=self.revealed)
        else:
            return notices.change_reveal(
                name_or_line=self.name,
                modify=lambda original: original.clone(msg=f'Revealed type is "{self.revealed}"'),
            )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Error:
    name: str
    error: str
    error_type: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        if self.append:
            return notices.add_error(
                name_or_line=self.name, error_type=self.error_type, error=self.error
            )
        else:
            return notices.change_error(
                name_or_line=self.name,
                modify=lambda original: original.clone(tag=self.error_type, msg=self.error),
            )


@dataclasses.dataclass(frozen=True, kw_only=True)
class SetErrors:
    name: str
    errors: Mapping[str, str]

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        line_number, line_notices, _ = notices.find_for_name_or_line(name_or_line=self.name)

        notices = notices.set_line_notices(
            line_number,
            line_notices.remove(
                lambda original: (
                    original.severity != "note" and not original.msg.startswith("Revealed type is")
                ),
            ),
        )

        for error_type, error in self.errors.items():
            notices = notices.add_error(name_or_line=self.name, error_type=error_type, error=error)

        return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class Note:
    name: str
    note: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        if self.append:
            return notices.add_note(name_or_line=self.name, note=self.note)
        else:
            return notices.change_note(
                name_or_line=self.name, modify=lambda original: original.clone(msg=self.note)
            )


@dataclasses.dataclass(frozen=True, kw_only=True)
class RemoveFromRevealedType:
    name: str
    remove: str

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        return notices.change_reveal(
            name_or_line=self.name,
            modify=lambda original: original.clone(msg=original.msg.replace(self.remove, "")),
        )


if TYPE_CHECKING:
    _E: protocols.FileNoticesChanger = cast(Error, None)
    _N: protocols.FileNoticesChanger = cast(Note, None)
    _RT: protocols.FileNoticesChanger = cast(RevealedType, None)
