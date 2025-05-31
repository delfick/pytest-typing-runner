from __future__ import annotations

import abc
import dataclasses
import fnmatch
import pathlib
import re
from collections import defaultdict
from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, ClassVar, Literal, cast, overload

from typing_extensions import Self, Unpack

from . import notice_changers, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class NoteSeverity:
    """
    Represents a "note" severity

    Implements :protocol:`pytest_typing_runner.protocols.Severity`
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
class WarningSeverity:
    """
    Represents a "warning" severity

    Implements :protocol:`pytest_typing_runner.protocols.Severity`
    """

    display: str = dataclasses.field(init=False, default="warning")

    def __lt__(self, other: protocols.Severity) -> bool:
        return self.display < other.display

    def __eq__(self, o: object) -> bool:
        other_display = getattr(o, "display", None)
        if not isinstance(other_display, str):
            return False

        return self.display == other_display


@dataclasses.dataclass(frozen=True)
class ErrorSeverity:
    """
    Represents an "error" severity with an error type

    The display will be ``error[ERROR_TYPE]`` and comparisons/ordering
    will take the ``error_type`` into account.

    Note that if the ``error_type`` is an empty string that comparisons with
    other severities will match any ``error_type``.

    Implements :protocol:`pytest_typing_runner.protocols.Severity`

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


class NoticeMsgBase(abc.ABC):
    """
    A notice msg that compares by treating the msg as a plain string
    """

    raw: str

    def __init__(self, raw: str, /) -> None:
        self.raw = raw

    def __str__(self) -> str:
        return str(self.raw)

    def __repr__(self) -> str:
        return repr(self.raw)

    def __eq__(self, o: object, /) -> bool:
        if isinstance(o, str):
            return o == self.raw
        else:
            return isinstance(o, type(self)) and o == self.raw

    def __lt__(self, o: protocols.NoticeMsg, /) -> bool:
        return self.raw < o.raw

    def __hash__(self) -> int:
        return hash(self.raw)

    def replace(self, old: str, new: str, count: int = -1, /) -> Self:
        return self.clone(pattern=self.raw.replace(old, new, count))

    @property
    @abc.abstractmethod
    def is_plain(self) -> bool: ...

    @classmethod
    @abc.abstractmethod
    def create(cls, *, pattern: str) -> Self: ...

    @abc.abstractmethod
    def match(self, *, want: str) -> bool: ...

    @abc.abstractmethod
    def clone(self, *, pattern: str) -> Self: ...

    def split_lines(self) -> Iterator[Self]:
        if "\n" not in self.raw:
            yield self
        else:
            for line in self.raw.split("\n"):
                yield self.clone(pattern=line)


class PlainMsg(NoticeMsgBase):
    """
    A notice msg that compares by treating the msg as a plain string

    .. code-block:: python

        from pytest_typing_runner import notices

        msg = notices.PlainMsg.create(pattern='Revealed type is "stuff"')
    """

    is_plain: ClassVar[bool] = True

    @classmethod
    def create(cls, *, pattern: str) -> Self:
        """
        Used to construct a GlobMsg

        Implements :protocol:`NoticeMsgMaker`
        """
        return cls(pattern)

    def match(self, *, want: str) -> bool:
        """
        Returns whether this msg exactly matches the wanted string.
        """
        return self == want

    def clone(self, *, pattern: str) -> Self:
        """
        Returns an instance of PlainMsg using the provided ``pattern``
        """
        return self.create(pattern=pattern)


class RegexMsg(NoticeMsgBase):
    """
    A notice msg that compares by treating the msg as a regex pattern

    .. code-block:: python

        from pytest_typing_runner import notices

        msg = notices.RegexMsg.create(pattern='Revealed type is "[^"]+"')
    """

    regex: re.Pattern[str]
    is_plain: ClassVar[bool] = False

    def __init__(self, raw: str, /) -> None:
        super().__init__(raw)
        self.regex = re.compile(str(self))

    @classmethod
    def create(cls, *, pattern: str) -> Self:
        """
        Used to construct a RegexMsg

        Implements :protocol:`NoticeMsgMaker`
        """
        return cls(pattern)

    def match(self, *, want: str) -> bool:
        """
        Returns whether this msg successfully performs a regex match on the wanted string.
        """
        return self.regex.match(want) is not None

    def clone(self, *, pattern: str) -> Self:
        """
        Returns an instance of RegexMsg using the provided ``pattern``
        """
        return self.create(pattern=pattern)


class GlobMsg(NoticeMsgBase):
    """
    A notice msg that compares by treating the msg as a glob pattern

    .. code-block:: python

        from pytest_typing_runner import notices

        msg = notices.RegexMsg.create(pattern='Revealed type is "*"')
    """

    is_plain: ClassVar[bool] = False

    @classmethod
    def create(cls, *, pattern: str) -> Self:
        """
        Used to construct a GlobMsg

        Implements :protocol:`NoticeMsgMaker`
        """
        return cls(pattern)

    def match(self, *, want: str) -> bool:
        """
        Returns whether this msg successfully performs a glob match on the wanted string.
        """
        return fnmatch.fnmatch(want, str(self))

    def clone(self, *, pattern: str) -> Self:
        """
        Returns an instance of GlobMsg using the provided ``pattern``
        """
        return self.create(pattern=pattern)


@dataclasses.dataclass(frozen=True, kw_only=True)
class NoticeMsgMakerMap:
    """
    Holds onto a map of names to msg makers.

    Implements :protocol:`pytest_tying_runner.protocols.NoticeMsgMakerMap`
    """

    makers: MutableMapping[str, protocols.NoticeMsgMaker] = dataclasses.field(
        default_factory=lambda: {
            "plain": PlainMsg.create,
            "regex": RegexMsg.create,
            "glob": GlobMsg.create,
        }
    )

    @overload
    def get(self, name: str, /, default: protocols.NoticeMsgMaker) -> protocols.NoticeMsgMaker: ...

    @overload
    def get(self, name: str, /, default: None = None) -> protocols.NoticeMsgMaker | None: ...

    def get(
        self, name: str, /, default: protocols.NoticeMsgMaker | None = None
    ) -> protocols.NoticeMsgMaker | None:
        return self.makers.get(name, default)

    @property
    def available(self) -> Sequence[str]:
        """
        Return the available msg makers
        """
        return list(self.makers)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProgramNotice:
    """
    Represents a single notice from the static type checker

    Implements :protocol:`pytest_typing_runner.protocols.ProgramNotice`

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
    msg: protocols.NoticeMsg

    @classmethod
    def create(
        cls,
        *,
        location: pathlib.Path,
        line_number: int,
        severity: protocols.Severity,
        msg: str | protocols.NoticeMsg,
        msg_maker: protocols.NoticeMsgMaker = PlainMsg.create,
        col: int | None = None,
    ) -> Self:
        if isinstance(msg, str):
            msg = msg_maker(pattern=msg)

        return cls(location=location, line_number=line_number, severity=severity, msg=msg, col=col)

    @classmethod
    def reveal_msg(cls, revealed: str, /) -> str:
        """
        Helper to get a string that represents the ``msg`` on a note for a ``reveal_type(...)`` instruction
        """
        return f'Revealed type is "{revealed}"'

    @property
    def is_type_reveal(self) -> bool:
        """
        Returns whether this notice represents output from a `reveal_type(...)` instruction
        """
        return self.severity == NoteSeverity() and self.msg.raw.startswith('Revealed type is "')

    def clone(
        self,
        *,
        msg: str | protocols.NoticeMsg | None = None,
        **kwargs: Unpack[protocols.ProgramNoticeCloneKwargs],
    ) -> Self:
        """
        Return a copy of this notice with certain values replaced.
        """
        if isinstance(msg, str):
            msg = self.msg.clone(pattern=msg)

        if msg is None:
            return dataclasses.replace(self, **kwargs)
        else:
            return dataclasses.replace(self, msg=msg, **kwargs)

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
        left = (self.location, self.line_number, self.display())
        right = (other.location, other.line_number, other.display())
        return left < right

    def matches(self, other: protocols.ProgramNotice) -> bool:
        """
        Compare against another program notice.

        If ``col`` is ``None`` on either notice then that is not compared.
        """
        same = (
            self.location == other.location
            and self.line_number == other.line_number
            and self.severity == other.severity
            and self.msg.match(want=other.msg.raw)
        )
        if not same:
            return False

        if self.col is None or other.col is None:
            return True

        return self.col == other.col


@dataclasses.dataclass(frozen=True, kw_only=True)
class LineNotices:
    """
    This represents the notices at a specific line in a specific file

    Implements :protocol:`pytest_typing_runner.protocols.LineNotices`

    :param location: The path these notices are for
    :param line_number: The specific line number for these notices
    """

    location: pathlib.Path
    line_number: int
    msg_maker: protocols.NoticeMsgMaker = PlainMsg.create

    notices: Sequence[protocols.ProgramNotice] = dataclasses.field(default_factory=list)

    @property
    def has_notices(self) -> bool:
        """
        Return whether this contains any notices
        """
        return bool(self.notices)

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        """
        Yield all the notices for this line
        """
        yield from self.notices

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
        """
        Return a copy where the chosen notice(s) are replaced

        :param notices: The notices the clone should have. Any None entries are dropped
        :param allow_empty: If False then None is returned instead of a copy with an empty list
        """
        replacement = [n for n in notices if n is not None]
        if not replacement:
            if not allow_empty:
                return None
        return dataclasses.replace(self, notices=replacement)

    def generate_notice(
        self,
        *,
        msg: str | protocols.NoticeMsg,
        msg_maker: protocols.NoticeMsgMaker | None = None,
        severity: protocols.Severity | None = None,
        col: int | None = None,
    ) -> protocols.ProgramNotice:
        """
        Return an object that satisfies :protocol:`pytest_typing_runner.protocols.ProgramNotice`

        :param severity: optional severity, defaults to "note"
        :param msg: optional msg, defaults to an empty string
        :param col: optional column, defaults to ``None``
        """
        if severity is None:
            severity = NoteSeverity()

        if msg_maker is None:
            msg_maker = self.msg_maker

        return ProgramNotice.create(
            location=self.location,
            line_number=self.line_number,
            severity=severity,
            msg=msg,
            col=col,
            msg_maker=msg_maker,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileNotices:
    """
    Used to represent the notices for a file

    Implements :protocol:`pytest_typing_runner.protocols.FileNotices`

    :param location: The location of the file the notices are in
    """

    location: pathlib.Path
    by_line_number: Mapping[int, protocols.LineNotices] = dataclasses.field(default_factory=dict)
    name_to_line_number: Mapping[str, int] = dataclasses.field(default_factory=dict)
    msg_maker: protocols.NoticeMsgMaker = PlainMsg.create

    @property
    def has_notices(self) -> bool:
        """
        Return True if there are there any notices for this file
        """
        return any(notices for notices in self.by_line_number.values() if notices.has_notices)

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        """
        Yield all the notices for the file
        """
        for _, notices in sorted(self.by_line_number.items()):
            yield from notices

    def known_line_numbers(self) -> Iterator[int]:
        """
        Yield the line numbers that have line notices
        """
        yield from sorted(self.by_line_number.keys())

    @property
    def known_names(self) -> Mapping[str, int]:
        """
        Return the registered names
        """
        return dict(self.name_to_line_number)

    def get_line_number(self, name_or_line: str | int, /) -> int | None:
        """
        Normalise a name or line number to a line number.

        The result has no relation to whether there are any notices for this file

        :param name_or_line:
            When this is an integer it is returned as is regardless of whether it is
            named or has associated notices.

            When it is a string, it will see if it is a registered name and either
            return ``None`` if it is not registered, else return the associated
            line number.
        """
        if isinstance(name_or_line, int):
            return name_or_line

        name = name_or_line
        if name not in self.name_to_line_number:
            return None

        return self.name_to_line_number[name]

    def notices_at_line(self, line_number: int) -> protocols.LineNotices | None:
        """
        Return ``None`` if there are no line notices for that line number, else
        return the found line notices.

        Note that if there is an empty line notices that will be returned instead
        of None.
        """
        if line_number not in self.by_line_number:
            return None

        return self.by_line_number[line_number]

    def generate_notices_for_line(
        self, line_number: int, *, msg_maker: protocols.NoticeMsgMaker | None = None
    ) -> protocols.LineNotices:
        """
        Return an object that satisfies :protocol:`pytest_typing_runner.protocols.LineNotices`
        for the location of this file at the specified line number.

        This object is not added to this file notices
        """
        if msg_maker is None:
            msg_maker = self.msg_maker
        return LineNotices(location=self.location, line_number=line_number, msg_maker=msg_maker)

    def set_name(self, name: str, line_number: int) -> Self:
        """
        Return a copy of the file notices with this ``name`` registered for
        the specified ``line_number``. If the ``name`` is already registered it
        will be overridden.
        """
        return dataclasses.replace(
            self, name_to_line_number={**self.name_to_line_number, name: line_number}
        )

    def set_lines(self, notices: Mapping[int, protocols.LineNotices | None]) -> Self:
        """
        Return a copy of this file notices with the notices replaced by those
        provided.

        When the value is ``None`` any notices for that line number will be
        removed.
        """
        replacement = dict(self.by_line_number)
        for line_number, line_notices in notices.items():
            if line_notices is None:
                replacement.pop(line_number, None)
            else:
                replacement[line_number] = line_notices

        return dataclasses.replace(self, by_line_number=replacement)

    def clear(self, *, clear_names: bool) -> Self:
        """
        Return a modified file notices with all notices removed
        """
        return dataclasses.replace(
            self,
            by_line_number={},
            name_to_line_number={} if clear_names else dict(self.name_to_line_number),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiffFileNotices:
    """
    Used to represent the notices for many lines of a single file between two
    runs of a type checker

    Implements :protocol:`pytest_typing_runner.protocols.DiffFileNotices`
    """

    by_line_number: Mapping[
        int, tuple[Sequence[protocols.ProgramNotice], Sequence[protocols.ProgramNotice]]
    ]

    def __iter__(
        self,
    ) -> Iterator[
        tuple[int, Sequence[protocols.ProgramNotice], Sequence[protocols.ProgramNotice]]
    ]:
        for line_number, (left_notices, right_notices) in sorted(self.by_line_number.items()):
            yield line_number, left_notices, right_notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiffNotices:
    """
    Used to represent the notices for many files between two runs of a type checker

    Implements :protocol:`pytest_typing_runner.protocols.DiffNotices`
    """

    by_file: Mapping[str, protocols.DiffFileNotices]

    def __iter__(self) -> Iterator[tuple[str, protocols.DiffFileNotices]]:
        yield from sorted(self.by_file.items())


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProgramNotices:
    """
    Represents all the notices for a run of a static type checker

    Implements :protocol:`pytest_typing_runner.protocols.ProgramNotices`
    """

    notices: Mapping[pathlib.Path, protocols.FileNotices] = dataclasses.field(default_factory=dict)
    msg_maker: protocols.NoticeMsgMaker = PlainMsg.create

    @property
    def has_notices(self) -> bool:
        """
        Return whether there are any notices
        """
        return any(notices for notices in self.notices.values() if notices.has_notices)

    def __iter__(self) -> Iterator[protocols.ProgramNotice]:
        """
        Yield all program notices
        """
        for _, notices in sorted(self.notices.items()):
            yield from notices

    def known_locations(self) -> Iterator[pathlib.Path]:
        """
        Yield locations that have associated file notices
        """
        yield from sorted(self.notices.keys())

    def diff(
        self, root_dir: pathlib.Path, other: protocols.ProgramNotices
    ) -> protocols.DiffNotices:
        """
        Produce a diff where this program notices is on the left, and the notices
        passed in is on the right.

        All locations across both will appear in the diff as strings relative to
        the passed in ``root_dir``.

        :param root_dir:
            All locations will be represented as a string relative to the ``root_dir``
            except for paths outside of ``root_dir`` which will be a string of
            the full path
        :param other: The right side of the diff
        """
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

                into[path][notice.line_number].append(notice)

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
        """
        Return the FileNotices for the specified ``location`` or ``None`` if
        no existing notices for that location.

        Note if there is an empty FileNotices for that location it will be
        returned instead of ``None``

        :param location: The location to return notices for
        """
        return self.notices.get(location)

    def generate_notices_for_location(
        self,
        location: pathlib.Path,
        *,
        msg_maker: protocols.NoticeMsgMaker | None = None,
    ) -> protocols.FileNotices:
        """
        Return an object that satisfies :protocol:`pytest_typing_runner.protocols.FileNotices`

        Note the file notices are not added to this ProgramNotices.

        :param location: The value set on the FileNotices for ``location``
        """
        if msg_maker is None:
            msg_maker = self.msg_maker
        return FileNotices(location=location, msg_maker=msg_maker)

    def set_files(self, notices: Mapping[pathlib.Path, protocols.FileNotices | None]) -> Self:
        """
        Return a copy of this ProgramNotices overriding the notices with those passed in

        Note that ``None`` values will result in that location being removed.

        Locations that exist but aren't in the passed in notices will be
        preserved

        :param notices:
            A map of location to either FileNotices to set for that location or
            ``None`` when that location should be removed.
        """
        replacement = dict(self.notices)
        for location, file_notices in notices.items():
            if file_notices is None:
                replacement.pop(location, None)
            else:
                replacement[location] = file_notices

        return dataclasses.replace(self, notices=replacement)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AddRevealedTypes:
    """
    Used to add revealed type notices to a specific line

    .. code-block:: python

        from pytest_typing_runner import notices, protocols


        file_notices: protocols.FileNotices = ...
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
        ]
        assert file_notices.get_line_number("line_name") == 1

        changed = notices.AddRevealedTypes(
            name="line_name",
            revealed=["two", "three"],
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
            'severity=note:: Revealed type is "two"',
            'severity=note:: Revealed type is "three"',
        ]

    Where existing revealed notes can be removed. For example, continuing the code example:

    .. code-block:: python

        changed = notices.AddRevealedTypes(
            name="line_name",
            revealed=["two", "three"],
            replace=True
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
            'severity=note:: Revealed type is "two"',
            'severity=note:: Revealed type is "three"',
        ]

    .. note::
        When there are multiple items in revealed, only one notice is appended
        where the different notes are in a single multiline string for the msg
        of that one notice. The default implementation for comparing notices already
        knows how to split these into multiple notices.

    :param name:
        The name of the line to change. The name must already be registered
    :param revealed:
        A sequence of strings to add reveal messages for. Each message is wrapped
        such that if the string is 'X' the result is 'Revealed type is "X"'
    :param replace:
        Defaults to ``False``. When ``True`` any existing reveal notes will be
        removed before new ones are added.
    """

    name: str
    revealed: Sequence[str]
    replace: bool = False

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        """
        Peforms the transformation

        :param notices: The file notices to change
        :raises MissingNotices:
            When the specified ``name`` isn't registered with the file notices.
        :returns:
            Copy of the file notices with additional reveal notes, where existing reveal
            notes have been removed if ``replace`` is ``True``
        """

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
                    [(None if notice.is_type_reveal else notice) for notice in notices],
                    allow_empty=True,
                )

            return notice_changers.AppendToLine(notices_maker=make_notices)(notices)

        return notice_changers.ModifyLine(
            name_or_line=self.name, name_must_exist=True, line_must_exist=False, change=change
        )(notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AddErrors:
    """
    Used to add error notices to a specific line

    .. code-block:: python

        from pytest_typing_runner import notices, protocols


        file_notices: protocols.FileNotices = ...
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
        ]
        assert file_notices.get_line_number("line_name") == 1

        changed = notices.AddErrors(
            name="line_name",
            errors=[("misc", "error two"), ("assignment", "error three")],
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
            'severity=error[misc]:: error two',
            'severity=error[assignment]:: error three',
        ]

    Where existing errors can be removed. For example, continuing the code example:

    .. code-block:: python

        changed = notices.AddErrors(
            name="line_name",
            errors=[("misc", "error two"), ("assignment", "error three")],
            replace=True,
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=note:: a note',
            'severity=error[misc]:: error two',
            'severity=error[assignment]:: error three',
        ]

    .. note::
        Unlike :class:`AddRevealedTypes` every entry in ``errors`` becomes it's
        own notice.

    :param name:
        The name of the line to change. The name must already be registered
    :param errors:
        A sequence of two string tuples where the first string is the error type
        and the second string is the error message.
    :param replace:
        Defaults to ``False``. When ``True`` any existing error notices will be
        removed before new ones are added.
    """

    name: str
    errors: Sequence[tuple[str, str | protocols.NoticeMsg]]
    replace: bool = False

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        """
        Peforms the transformation

        :param notices: The file notices to change
        :raises MissingNotices:
            When the specified ``name`` isn't registered with the file notices.
        :returns:
            Copy of the file notices with additional error notices, where existing error
            notices have been removed if ``replace`` is ``True``
        """

        def make_notices(
            notices: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [
                notices.generate_notice(severity=ErrorSeverity(error_type), msg=error)
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
    """
    Used to add note notices to a specific line

    .. code-block:: python

        from pytest_typing_runner import notices, protocols


        file_notices: protocols.FileNotices = ...
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
        ]
        assert file_notices.get_line_number("line_name") == 1

        changed = notices.AddNotes(
            name="line_name",
            notes=["two", "three"],
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a note',
            'severity=note:: two',
            'severity=note:: three',
        ]

    Where existing notes can be removed. For example, continuing the code example:

    .. code-block:: python

        changed = notices.AddNotes(
            name="line_name",
            notes=["two", "three"],
            replace=True,
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=error[arg-type]:: an error',
            'severity=note:: two',
            'severity=note:: three',
        ]

    And existing reveal notes can be left alone, continuing the code example:

    .. code-block:: python

        changed = notices.AddNotes(
            name="line_name",
            notes=["two", "three"],
            replace=True,
            keep_reveals=True,
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "one"',
            'severity=error[arg-type]:: an error',
            'severity=note:: two',
            'severity=note:: three',
        ]

    .. note::
        Like :class:AddRevealedTypes: only one notice is append to the end
        where the message is a multiline string with each note on it's own line

    :param name:
        The name of the line to change. The name must already be registered
    :param notes:
        A sequence of strings representing each note to add
    :param replace:
        Defaults to ``False``. When ``True`` any existing notes removed before new
        ones are added.
    :param keep_reveals:
        Defaults to ``True``. When ``replace`` is ``True`` and this is ``True`` then notes
        that are type reveals will not be removed.
    """

    name: str
    notes: Sequence[str | protocols.NoticeMsg]
    replace: bool = False
    keep_reveals: bool = True

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        """
        Peforms the transformation

        :param notices: The file notices to change
        :raises MissingNotices:
            When the specified ``name`` isn't registered with the file notices.
        :returns:
            Copy of the file notices with additional notes, where existing notes are removed
            depending on the values of ``replace`` and ``keep_reveals``.
        """

        def make_notices(
            notices: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            notes = self.notes
            if all(isinstance(note, str) for note in notes):
                notes = ["\n".join(str(note) for note in self.notes)]

            return [notices.generate_notice(severity=NoteSeverity(), msg=note) for note in notes]

        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            if self.replace:
                replaced: list[protocols.ProgramNotice | None] = []
                for notice in notices:
                    if notice.severity == NoteSeverity():
                        if self.keep_reveals and notice.is_type_reveal:
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
    """
    Used to remove some specific string from existing reveal notes.

    .. code-block:: python

        from pytest_typing_runner import notices, protocols


        file_notices: protocols.FileNotices = ...
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "some specific message"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a specific note',
        ]
        assert file_notices.get_line_number("line_name") == 1

        changed = notices.RemoveFromRevealedType(
            name="line_name",
            remove="specific",
        )(file_notices)
        assert [n.display() for n in file_notices.notices_at_line(1)] == [
            'severity=note:: Revealed type is "some  message"',
            'severity=error[arg-type]:: an error',
            'severity=note:: a specific note',
        ]

    :param name:
        The name of the line to change. The name must already be registered
    :param remove:
        The string to remove from all reveal notes that are found.
    :param must_exist:
        Defaults to ``True``. When ``True`` and no reveal notes are found with the specified
        ``replace`` string, then :class:`MissingNotices` will be raised.
    """

    name: str
    remove: str
    must_exist: bool = True

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        """
        Peforms the transformation

        :param notices: The file notices to change
        :raises MissingNotices:
            When the specified ``name`` isn't registered with the file notices.
        :raises MissingNotices:
            When ``must_exist`` is ``True`` and no reveal notes with the ``replace`` string are found
        :returns:
            Copy of the file notices where all revealed notes at the specified line have the
            ``replace`` string removed from their ``msg``.
        """

        def change(notices: protocols.LineNotices, /) -> protocols.LineNotices | None:
            found: bool = False
            replaced: list[protocols.ProgramNotice | None] = []
            for notice in notices:
                if notice.is_type_reveal:
                    if self.remove in notice.msg.raw:
                        found = True
                        notice = notice.clone(msg=notice.msg.replace(self.remove, ""))
                replaced.append(notice)

            if not found and self.must_exist:
                raise notice_changers.MissingNotices(
                    location=notices.location, line_number=notices.line_number, name=self.name
                )

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

    _N: protocols.FileNoticesChanger = cast(AddNotes, None)
    _E: protocols.FileNoticesChanger = cast(AddErrors, None)
    _SE: protocols.FileNoticesChanger = cast(AddRevealedTypes, None)
    _RFRT: protocols.FileNoticesChanger = cast(RemoveFromRevealedType, None)

    _NS: protocols.Severity = cast(NoteSeverity, None)
    _ES: protocols.Severity = cast(ErrorSeverity, None)

    _EC: protocols.NoticeMsg = cast(PlainMsg, None)
    _ECM: protocols.NoticeMsgMaker = PlainMsg.create
    _RC: protocols.NoticeMsg = cast(RegexMsg, None)
    _RCM: protocols.NoticeMsgMaker = RegexMsg.create
    _GC: protocols.NoticeMsg = cast(GlobMsg, None)
    _GCM: protocols.NoticeMsgMaker = GlobMsg.create

    _NMM: protocols.NoticeMsgMakerMap = cast(NoticeMsgMakerMap, None)
