import dataclasses
import pathlib
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Generic, Literal, cast, overload

from typing_extensions import Self, Unpack

from . import protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunResult(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunResult.
    """

    options: protocols.RunOptions[protocols.T_Scenario]
    exit_code: int
    stdout: str
    stderr: str

    @classmethod
    def from_options(
        cls,
        options: protocols.RunOptions[protocols.T_Scenario],
        exit_code: int,
        *,
        stdout: str,
        stderr: str,
    ) -> Self:
        return cls(options=options, exit_code=exit_code, stdout=stdout, stderr=stderr)


@dataclasses.dataclass(kw_only=True)
class ProgramNotice:
    """
    Represents a single notice from the static type checker
    """

    location: pathlib.Path
    line_number: int
    col: int | None
    severity: str
    tag: str | None
    msg: str

    def for_compare(self) -> Iterator[Self]:
        yield self

    def clone(self, **kwargs: Unpack[protocols.ProgramNoticeCloneKwargs]) -> Self:
        return dataclasses.replace(self, **kwargs)

    def display(self) -> str:
        # TODO Implement
        return ""

    def __lt__(self, other: protocols.ProgramNotice) -> bool:
        return self.display() < other.display()

    def matches(self, other: protocols.ProgramNotice) -> bool:
        # TODO: implement
        return True


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
        # TODO: implement
        return self

    def replace(
        self,
        chooser: protocols.ProgramNoticeChooser,
        *,
        replaced: protocols.ProgramNotice,
        first_only: bool = True,
    ) -> Self:
        # TODO: implement
        return self

    def remove(self, chooser: protocols.ProgramNoticeChooser) -> Self:
        # TODO: implement
        return self


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

    def notices_for_line_number(self, line_number: int) -> protocols.LineNotices | None:
        if line_number not in self.by_line_number:
            return None

        return self.by_line_number[line_number]

    def set_line_notices(self, line_number: int, notices: protocols.LineNotices) -> Self:
        # TODO implement
        return self

    def add_notice(self, line_number: int, notice: protocols.ProgramNotice) -> Self:
        # TODO implement
        return self

    def set_name(self, name: str, line_number: int) -> Self:
        # TODO implement
        return self

    @overload
    def find_for_name_or_line(
        self, *, name_or_line: str | int, severity: str | None = None, must_exist: Literal[True]
    ) -> tuple[int, protocols.LineNotices, protocols.ProgramNotice]: ...

    @overload
    def find_for_name_or_line(
        self,
        *,
        name_or_line: str | int,
        severity: str | None = None,
        must_exist: Literal[False] = False,
    ) -> tuple[int, protocols.LineNotices, protocols.ProgramNotice | None]: ...

    def find_for_name_or_line(
        self, *, name_or_line: str | int, severity: str | None = None, must_exist: bool = False
    ) -> tuple[int, protocols.LineNotices, protocols.ProgramNotice | None]:
        # TODO: implement
        return 0, LineNotices(line_number=0, location=self.location), None

    def add_reveal(self, *, name_or_line: str | int, revealed: str) -> Self:
        # TODO implement
        return self

    def change_reveal(
        self, *, name_or_line: str | int, modify: protocols.ProgramNoticeModify
    ) -> Self:
        # TODO implement
        return self

    def add_error(self, *, name_or_line: str | int, error_type: str, error: str) -> Self:
        # TODO implement
        return self

    def change_error(
        self, *, name_or_line: str | int, modify: protocols.ProgramNoticeModify
    ) -> Self:
        # TODO implement
        return self

    def add_note(self, *, name_or_line: str | int, note: str) -> Self:
        # TODO implement
        return self

    def change_note(
        self, *, name_or_line: str | int, modify: protocols.ProgramNoticeModify
    ) -> Self:
        # TODO implement
        return self

    def remove_notices(
        self, *, name_or_line: str | int, chooser: protocols.ProgramNoticeChooser
    ) -> Self:
        # TODO implement
        return self


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
        # TODO: impelement
        return DiffNotices(by_file={})


@dataclasses.dataclass(frozen=True, kw_only=True)
class Expectations(Generic[protocols.T_Scenario]):
    options: protocols.RunOptions[protocols.T_Scenario]

    expect_fail: bool
    expect_stderr: str = ""
    expect_notices: ProgramNotices = dataclasses.field(default_factory=ProgramNotices)

    def check_results(self, result: protocols.RunResult[protocols.T_Scenario]) -> None:
        # TODO: implement
        return

    @classmethod
    def success_expectation(
        cls,
        scenario_runner: protocols.ScenarioRunner[protocols.T_Scenario],
        options: protocols.RunOptions[protocols.T_Scenario],
    ) -> Self:
        return cls(options=options, expect_fail=False)


if TYPE_CHECKING:
    _RR: protocols.RunResult[protocols.P_Scenario] = cast(RunResult[protocols.P_Scenario], None)

    _E: protocols.P_Expectations = cast(Expectations[protocols.P_Scenario], None)

    _FN: protocols.FileNotices = cast(FileNotices, None)
    _LN: protocols.LineNotices = cast(LineNotices, None)
    _PN: protocols.ProgramNotice = cast(ProgramNotice, None)
    _DN: protocols.DiffNotices = cast(DiffNotices, None)
    _DFN: protocols.DiffFileNotices = cast(DiffFileNotices, None)
