from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Callable, MutableMapping, Sequence
from typing import TYPE_CHECKING, Literal, cast, overload

from . import errors, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class MissingNotices(errors.PyTestTypingRunnerException):
    location: pathlib.Path
    name: str | int | None = None
    line_number: int | None = None

    def __str__(self) -> str:
        line = ""
        if self.line_number is not None:
            line = f":{self.line_number}"
        if isinstance(self.name, str):
            line = f"{line} ({self.name})"
        return f"Failed to find registered notices for {self.location}{line}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class FirstMatchOnly:
    change: protocols.ProgramNoticeChanger[protocols.ProgramNotice]
    found: MutableMapping[None, None] = dataclasses.field(init=False, default_factory=dict)

    def __call__(self, notice: protocols.ProgramNotice, /) -> protocols.ProgramNotice | None:
        if None in self.found:
            return notice

        self.found[None] = None
        return self.change(notice)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ChangeOnMatch:
    msg_prefix: str
    match_severity: protocols.Severity
    change: protocols.ProgramNoticeChanger[protocols.ProgramNotice]

    def __call__(self, notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
        replacement: list[protocols.ProgramNotice | None] = []
        for notice in notices:
            matched = self.match_severity == notice.severity and notice.msg.startswith(
                self.msg_prefix
            )
            if matched:
                replacement.append(self.change(notice))
            else:
                replacement.append(notice)

        return notices.set_notices(replacement)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AppendToLine:
    notices_maker: Callable[[protocols.LineNotices], Sequence[protocols.ProgramNotice | None]]

    def __call__(self, notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
        return notices.set_notices([*list(notices), *self.notices_maker(notices)])


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyLatestMatch:
    must_exist: bool = False
    change: protocols.ProgramNoticeChanger[protocols.ProgramNotice]
    matcher: Callable[[protocols.ProgramNotice], bool]

    def __call__(self, notices: protocols.LineNotices) -> protocols.LineNotices | None:
        replaced: list[protocols.ProgramNotice | None] = []
        found: bool = False
        for notice in reversed(list(notices)):
            if found:
                replaced.append(notice)
                continue

            if self.matcher(notice):
                found = True
                replaced.append(self.change(notice))

        if not found:
            if self.must_exist:
                raise MissingNotices(line_number=notices.line_number, location=notices.location)
            replaced.append(self.change(notices.generate_notice()))

        return notices.set_notices(replaced)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyLine:
    name_or_line: str | int
    name_must_exist: bool = True
    line_must_exist: bool = True
    change: protocols.ProgramNoticeChanger[protocols.LineNotices]

    @overload
    def __call__(
        self, notices: protocols.FileNotices, /, *, allow_empty: Literal[True]
    ) -> protocols.FileNotices: ...

    @overload
    def __call__(
        self, notices: protocols.FileNotices, /, *, allow_empty: Literal[False] = False
    ) -> protocols.FileNotices | None: ...

    def __call__(
        self, notices: protocols.FileNotices, /, *, allow_empty: bool = False
    ) -> protocols.FileNotices | None:
        line_notices: protocols.LineNotices | None = None
        line_number = notices.get_line_number(self.name_or_line)
        if line_number is not None:
            line_notices = notices.notices_at_line(line_number)

        if line_number is None and self.name_must_exist:
            raise MissingNotices(
                line_number=line_number, name=self.name_or_line, location=notices.location
            )

        if line_notices is None and self.line_must_exist:
            raise MissingNotices(
                line_number=line_number, name=self.name_or_line, location=notices.location
            )

        if line_number is None:
            return notices

        if line_notices is None:
            line_notices = notices.generate_notices_for_line(line_number)

        change = {line_number: self.change(line_notices)}
        if allow_empty:
            # Statically pass in True to make the return type statically correct
            return notices.set_lines(change, allow_empty=True)
        else:
            return notices.set_lines(change, allow_empty=False)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyFile:
    location: pathlib.Path
    must_exist: bool = True
    change: protocols.ProgramNoticeChanger[protocols.FileNotices]

    def __call__(self, notices: protocols.ProgramNotices) -> protocols.ProgramNotices:
        file_notices = notices.notices_at_location(self.location)
        if file_notices is None and self.must_exist:
            raise MissingNotices(location=self.location)

        if file_notices is None:
            file_notices = notices.generate_notices_for_location(self.location)

        return notices.set_files({self.location: self.change(file_notices)})


if TYPE_CHECKING:
    _FMO: protocols.ProgramNoticeChanger[protocols.ProgramNotice] = cast(FirstMatchOnly, None)
    _COM: protocols.ProgramNoticeChanger[protocols.LineNotices] = cast(ChangeOnMatch, None)
    _ATL: protocols.ProgramNoticeChanger[protocols.LineNotices] = cast(AppendToLine, None)
    _ATLM: protocols.ProgramNoticeChanger[protocols.LineNotices] = cast(ModifyLatestMatch, None)
    _ML: protocols.ProgramNoticeChanger[protocols.FileNotices] = cast(ModifyLine, None)
    _MF: protocols.ProgramNoticesChanger = cast(ModifyFile, None)
