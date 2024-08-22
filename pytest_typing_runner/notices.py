from __future__ import annotations

import dataclasses
import pathlib
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, cast, overload

from typing_extensions import Self, Unpack

from . import notice_changers, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class NoteSeverity:
    """
    Represents a "note" severity
    """

    display: str = dataclasses.field(init=False, default="note")

    def __lt__(self, other: protocols.Severity) -> bool:
        return self.display < other.display

    def __eq__(self, o: object) -> bool:
        other_display = getattr(o, "display", None)
        if not isinstance(other_display, str):
            return False

        return self.display == other_display


@dataclasses.dataclass(frozen=True, kw_only=True)
class ErrorSeverity:
    """
    Represents an "error" severity with an error type

    The display will be ``error[ERROR_TYPE]`` and comparisons/ordering
    will take the ``error_type`` into account.

    Note that if the ``error_type`` is an empty string that comparisons with
    other severities will match any ``error_type``.

    :param error_type: The specific type of error. For example ``arg-type`` or ``assignment``
    """

    error_type: str

    def __eq__(self, o: object) -> bool:
        """
        This is equal to another object if that object has ``.display`` as a string
        that is ``error[error_type]``.

        If ``self.error_type`` is an empty string then the ``[error_type]`` on the object
        being compared to will be ignored.
        """
        other_display = getattr(o, "display", None)
        if not isinstance(other_display, str):
            return False

        if self.error_type == "":
            return other_display.startswith("error[") or other_display == "error"
        elif other_display in ("error", "error[]"):
            return True
        else:
            return other_display == self.display

    @property
    def display(self) -> str:
        """
        Display the error as ``error[{self.error_type}]``
        """
        return f"error[{self.error_type}]"

    def __lt__(self, other: protocols.Severity) -> bool:
        """
        Order by the ``display`` property
        """
        return self.display < other.display


@dataclasses.dataclass(kw_only=True)
class ProgramNotice:
    """
    Default implementation for :protocol:`pytest_typing_runner.protocols.ProgramNotices`

    Represents a single notice from the static type checker

    :param location: The full path to the file this notice is for
    :param line_number: the line this notice appears on
    :param col: optional line representing the column the error relates to
    :param severity: The severity of the notice (either note or error with a specific error type)
    :param msg: The message in the notice
    """

    location: pathlib.Path
    line_number: int
    col: int | None
    severity: protocols.Severity
    msg: str

    @classmethod
    def reveal_msg(cls, revealed: str, /) -> str:
        """
        Helper to get a string that represents the ``msg`` on a note for a ``reveal_type(...)`` instruction
        """
        return f'Revealed type is "{revealed}"'

    def clone(self, **kwargs: Unpack[protocols.ProgramNoticeCloneKwargs]) -> Self:
        """
        Return a copy of this notice with certain values replaced.
        """
        return dataclasses.replace(self, **kwargs)

    def display(self) -> str:
        """
        Return a string for displaying this notice.

        If ``col`` is None then it's not displayed.

        Will return "col=COL severity=SEVERITY:: MSG"
        """
        col = "" if self.col is None else f"col={self.col} "
        return f"{col}severity={self.severity.display}:: {self.msg}"

    def __lt__(self, other: protocols.ProgramNotice) -> bool:
        """
        Allow ordering against other notices in a sequence

        Orders by comparing the "display" string
        """
        return self.display() < other.display()

    def matches(self, other: protocols.ProgramNotice) -> bool:
        """
        Compare against another program notice.

        If ``col`` is ``None`` on either notice then that is not compared.
        """
        same = (
            self.location == other.location
            and self.line_number == other.line_number
            and self.severity == other.severity
            and self.msg == other.msg
        )
        if not same:
            return False

        if self.col is None or other.col is None:
            return True

        return self.col == other.col


@dataclasses.dataclass(frozen=True, kw_only=True)
class LineNotices:
    location: pathlib.Path
    line_number: int

    notices: Sequence[protocols.ProgramNotice] = dataclasses.field(default_factory=list)

    @property
    def has_notices(self) -> bool:
        return bool(self.notices)

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        yield from self.notices

    def add(self, notice: protocols.ProgramNotice) -> Self:
        return dataclasses.replace(self, notices=[*self.notices, notice])

    @overload
    def set_notices(
        self, notices: Sequence[protocols.ProgramNotice | None], allow_empty: Literal[True]
    ) -> Self: ...

    @overload
    def set_notices(
        self,
        notices: Sequence[protocols.ProgramNotice | None],
        allow_empty: Literal[False] = False,
    ) -> Self | None: ...

    def set_notices(
        self, notices: Sequence[protocols.ProgramNotice | None], allow_empty: bool = False
    ) -> Self | None:
        replacement = [n for n in notices if n is not None]
        if not replacement:
            if not allow_empty:
                return None
        return dataclasses.replace(self, notices=replacement)

    def generate_notice(
        self, *, severity: protocols.Severity | None = None, msg: str = "", col: int | None = None
    ) -> protocols.ProgramNotice:
        if severity is None:
            severity = NoteSeverity()
        return ProgramNotice(
            location=self.location,
            line_number=self.line_number,
            severity=severity,
            msg=msg,
            col=col,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileNotices:
    location: pathlib.Path
    by_line_number: Mapping[int, protocols.LineNotices] = dataclasses.field(default_factory=dict)
    name_to_line_number: Mapping[str, int] = dataclasses.field(default_factory=dict)

    @property
    def has_notices(self) -> bool:
        return any(notices for notices in self.by_line_number.values())

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        for _, notices in sorted(self.by_line_number.items()):
            yield from notices

    def get_line_number(self, name_or_line: str | int, /) -> int | None:
        if isinstance(name_or_line, int):
            return name_or_line

        name = name_or_line
        if name not in self.name_to_line_number:
            return None

        return self.name_to_line_number[name]

    def notices_at_line(self, line_number: int) -> protocols.LineNotices | None:
        if line_number not in self.by_line_number:
            return None

        return self.by_line_number[line_number]

    def generate_notices_for_line(self, line_number: int) -> protocols.LineNotices:
        return LineNotices(location=self.location, line_number=line_number)

    def set_name(self, name: str, line_number: int) -> Self:
        return dataclasses.replace(
            self, name_to_line_number={**self.name_to_line_number, name: line_number}
        )

    @overload
    def set_lines(
        self, notices: Mapping[int, protocols.LineNotices | None], allow_empty: Literal[True]
    ) -> Self: ...

    @overload
    def set_lines(
        self,
        notices: Mapping[int, protocols.LineNotices | None],
        allow_empty: Literal[False] = False,
    ) -> Self: ...

    def set_lines(
        self, notices: Mapping[int, protocols.LineNotices | None], allow_empty: bool = False
    ) -> Self | None:
        replacement = dict(self.by_line_number)
        for line_number, line_notices in notices.items():
            if line_notices is None:
                if line_number in replacement:
                    del replacement[line_number]
            else:
                replacement[line_number] = line_notices

        if not replacement:
            if allow_empty:
                return None

        return dataclasses.replace(self, by_line_number=replacement)


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiffFileNotices:
    by_line_number: Mapping[
        int, tuple[Sequence[protocols.ProgramNotice], Sequence[protocols.ProgramNotice]]
    ]

    def __iter__(
        self,
    ) -> Iterator[
        tuple[int, Sequence[protocols.ProgramNotice], Sequence[protocols.ProgramNotice]]
    ]:
        for line_number, (left_notices, right_notices) in sorted(self.by_line_number.items()):
            yield line_number, sorted(left_notices), sorted(right_notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiffNotices:
    by_file: Mapping[str, protocols.DiffFileNotices]

    def __iter__(self) -> Iterator[tuple[str, protocols.DiffFileNotices]]:
        yield from sorted(self.by_file.items())


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProgramNotices:
    notices: Mapping[pathlib.Path, protocols.FileNotices] = dataclasses.field(default_factory=dict)

    @property
    def has_notices(self) -> bool:
        return any(notices for notices in self.notices.values())

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        for _, notices in sorted(self.notices.items()):
            yield from notices

    def diff(
        self, root_dir: pathlib.Path, other: protocols.ProgramNotices
    ) -> protocols.DiffNotices:
        by_file_left: dict[str, dict[int, list[protocols.ProgramNotice]]] = defaultdict(
            lambda: defaultdict(list)
        )
        by_file_right: dict[str, dict[int, list[protocols.ProgramNotice]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for notices, into in ((self, by_file_left), (other, by_file_right)):
            for notice in notices:
                if notice.location.is_relative_to(root_dir):
                    path = str(notice.location.relative_to(root_dir))
                else:
                    path = str(notice.location)

                for line in notice.msg.split("\n"):
                    into[path][notice.line_number].append(notice.clone(msg=line))

        final: dict[
            str, dict[int, tuple[list[protocols.ProgramNotice], list[protocols.ProgramNotice]]]
        ] = defaultdict(lambda: defaultdict(lambda: ([], [])))

        for index, frm in ((0, by_file_left), (1, by_file_right)):
            for path, by_line in frm.items():
                for line_number, ns in by_line.items():
                    final[path][line_number][index].extend(ns)

        return DiffNotices(
            by_file={
                path: DiffFileNotices(by_line_number=by_line_number)
                for path, by_line_number in final.items()
            }
        )

    def notices_at_location(self, location: pathlib.Path) -> protocols.FileNotices | None:
        return self.notices.get(location)

    def generate_notices_for_location(self, location: pathlib.Path) -> protocols.FileNotices:
        return FileNotices(location=location)

    def set_files(self, notices: Mapping[pathlib.Path, protocols.FileNotices | None]) -> Self:
        replacement = dict(self.notices)
        for location, file_notices in notices.items():
            if file_notices is None:
                if location in replacement:
                    del replacement[location]
            else:
                replacement[location] = file_notices

        return dataclasses.replace(self, notices=replacement)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AddRevealedTypes:
    name: str
    revealed: Sequence[str]
    replace: bool = False

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices | None:
        def make_notices(
            notices: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [
                notices.generate_notice(
                    severity=NoteSeverity(),
                    msg="\n".join(
                        [ProgramNotice.reveal_msg(revealed) for revealed in self.revealed]
                    ),
                )
            ]

        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            if self.replace:
                notices = notices.set_notices(
                    [
                        (
                            None
                            if (
                                notice.severity == NoteSeverity()
                                and notice.msg.startswith("Revealed type is")
                            )
                            else notice
                        )
                        for notice in notices
                    ],
                    allow_empty=True,
                )

            return notice_changers.AppendToLine(notices_maker=make_notices)(notices)

        return notice_changers.ModifyLine(
            name_or_line=self.name, name_must_exist=True, line_must_exist=False, change=change
        )(notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AddErrors:
    name: str
    errors: Sequence[tuple[str, str]]
    replace: bool = False

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices | None:
        def make_notices(
            notices: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [
                notices.generate_notice(severity=ErrorSeverity(error_type=error_type), msg=error)
                for error_type, error in self.errors
            ]

        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            if self.replace:
                notices = notices.set_notices(
                    [
                        (None if notice.severity.display.startswith("error") else notice)
                        for notice in notices
                    ],
                    allow_empty=True,
                )
            return notice_changers.AppendToLine(notices_maker=make_notices)(notices)

        return notice_changers.ModifyLine(
            name_or_line=self.name, name_must_exist=True, line_must_exist=False, change=change
        )(notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AddNotes:
    name: str
    notes: Sequence[str]
    replace: bool = False
    keep_reveals: bool = True

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices | None:
        def make_notices(
            notices: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [
                notices.generate_notice(severity=NoteSeverity(), msg=note) for note in self.notes
            ]

        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            if self.replace:
                replaced: list[protocols.ProgramNotice | None] = []
                for notice in notices:
                    if notice.severity == NoteSeverity():
                        if self.keep_reveals and notice.msg.startswith("Revealed type is"):
                            replaced.append(notice)
                    else:
                        replaced.append(notice)

                notices = notices.set_notices(replaced, allow_empty=True)

            return notice_changers.AppendToLine(notices_maker=make_notices)(notices)

        return notice_changers.ModifyLine(
            name_or_line=self.name, name_must_exist=True, line_must_exist=False, change=change
        )(notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class RemoveFromRevealedType:
    name: str
    remove: str

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices | None:
        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            replaced: list[protocols.ProgramNotice | None] = []
            for notice in notices:
                if notice.severity == NoteSeverity() and notice.msg.startswith("Revealed type is"):
                    notice = notice.clone(msg=notice.msg.replace(self.remove, ""))
                replaced.append(notice)

            return notices.set_notices(replaced)

        return notice_changers.ModifyLine(
            name_or_line=self.name, name_must_exist=True, line_must_exist=False, change=change
        )(notices)


if TYPE_CHECKING:
    _FN: protocols.FileNotices = cast(FileNotices, None)
    _LN: protocols.LineNotices = cast(LineNotices, None)
    _PN: protocols.ProgramNotice = cast(ProgramNotice, None)
    _DN: protocols.DiffNotices = cast(DiffNotices, None)
    _DFN: protocols.DiffFileNotices = cast(DiffFileNotices, None)

    _N: protocols.ProgramNoticeChanger[protocols.FileNotices] = cast(AddNotes, None)
    _E: protocols.ProgramNoticeChanger[protocols.FileNotices] = cast(AddErrors, None)
    _SE: protocols.ProgramNoticeChanger[protocols.FileNotices] = cast(AddRevealedTypes, None)
    _RFRT: protocols.ProgramNoticeChanger[protocols.FileNotices] = cast(
        RemoveFromRevealedType, None
    )

    _NS: protocols.Severity = cast(NoteSeverity, None)
    _ES: protocols.Severity = cast(ErrorSeverity, None)
