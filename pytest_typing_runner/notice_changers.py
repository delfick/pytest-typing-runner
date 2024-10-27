from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, cast

from . import errors, protocols


@dataclasses.dataclass(kw_only=True)
class MissingNotices(errors.PyTestTypingRunnerException):
    """
    Raised when notices are expected to be somewhere they are not

    :param location: The file the notices were expected to be in
    :param name: Optional name of the line notices expected to be on
    :param line_number: Optional line number the notices were expected to be on
    """

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
    """
    Used to change a ProgramNotice such that only the first time this is used a change
    will be made:

    .. code-block:: python

        from pytest_typing_runner import notice_changers, protocols


        changer = notice_changers.FirstMatchOnly(
            change = lambda notice: notice.clone(msg="changed!")
        )

        existing_notice: protocols.ProgramNotice = ...
        changed_notice = changer(existing_notice)
        assert changed_notice is not existing_notice

        other_existing_notice: protocols.ProgramNotice = ...
        # subsequent changes will pass through existing notice
        changed_other_notice = changer(other_existing_notice)
        assert changed_other_notice is other_existing_notice

    :param change:
        A function that takes in a program notice and returns either ``None`` if
        the notice should be removed, or a program notice to replace it.

    .. automethod:: __call__
    """

    change: protocols.ProgramNoticeChanger
    found: MutableMapping[None, None] = dataclasses.field(init=False, default_factory=dict)

    def __call__(self, notice: protocols.ProgramNotice, /) -> protocols.ProgramNotice | None:
        """
        Perform the transformation

        :param notice: The notice to change
        :returns:
            Clone of the program notice with changes, or None if the notice should be deleted
        """
        if None in self.found:
            return notice

        self.found[None] = None
        return self.change(notice)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AppendToLine:
    """
    Used to append notices to a line notices.

    .. code-block:: python

        from pytest_typing_runner import notice_changer, protocols


        existing_line_notices: protocols.LineNotices = ...
        assert list(existing_line_notices) == [_existing_notice1, _existing_notice2]

        changer = notice_changer.AppendToLine(
            notices_maker = lambda ln: [_new_notice1, new_notice2]
        )

        changed = changer(existing_line_notices)
        assert list(existing_line_notices) == [_existing_notice1, _existing_notice2, _new_notice1, _new_notice2]

    :param notices_maker:
        Callable that takes the line notices being changed and returns a sequence
        of program notice objects to add to that line notices. Any ``None`` values
        in the sequence will be ignored.

    .. automethod:: __call__
    """

    notices_maker: Callable[[protocols.LineNotices], Sequence[protocols.ProgramNotice | None]]

    def __call__(self, notices: protocols.LineNotices, /) -> protocols.LineNotices:
        """
        Perform the transformation

        :param notices: The line notices to change
        :returns:
            A copy of the passed in notices with the additional notices appended.
            This changer never returns ``None``.
        """
        additional = self.notices_maker(notices)
        return notices.set_notices([*list(notices), *additional], allow_empty=True)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyLatestMatch:
    """
    Used to match against a particular notice and change the first one that matches
    where the matching happens from the end of the notices back.

    So if the line notices has ``[n1, n2, n3]`` then it will try to match ``n3``
    then ``n2``, then ``n1``. Once a notice has been changed, the rest will
    not be changed.

    By default if no notice matches then a new notice is added to the end and
    run through the `change` argument.

    .. code-block:: python

        from pytest_typing_runner import protocols, notice_changers


        line_notices: protocols.LineNotices = ...
        assert [n.msg for n in list(line_notices)] == ["n1", "s1", "n2", "s2", "n3"]

        changer = notice_changers.ModifyLatestMatch(
            change = lambda notice: notice.clone(msg="changed!"),
            matcher = lambda notice: notice.msg.startswith("s")
        )

        changed = changer(line_notices)
        assert [n.msg for n in (list(changed) or [])] == ["n1", "s1", "n2", "changed!", "n3"]

    :param must_exist:
        Defaults to ``False``, if passed in as ``True`` then an exception will
        be raised if no notice matches
    :param allow_empty:
        Defaults to ``False``, if passed in as ``True`` then this changer will
        never return ``None``. Otherwise if there are no notices in the line notices
        after the change, then ``None`` will be returned to indicate the notices
        should be deleted.
    :param change:
        A function to be given the notice to change. Note that if ``must_exist``
        is ``False`` and no notice matches, then it will be given a notice
        with a default "note" severity and empty message.
    :param matcher:
        A function given each notice from the back to the front till ``True``
        is returned to indicate a notice that should be changed

    .. automethod:: __call__
    """

    must_exist: bool = False
    allow_empty: bool = False
    change: protocols.ProgramNoticeChanger
    matcher: Callable[[protocols.ProgramNotice], bool]

    def __call__(self, notices: protocols.LineNotices) -> protocols.LineNotices | None:
        """
        Perform the transformation

        :param notices: The line notices to change
        :raises MissingNotices: if no notice matches and ``must_exist`` is True
        :returns:
            A copy of the line notices with the changed notice, or ``None`` if
            ``allow_empty`` is ``False`` and no notices are left after the change.
        """
        replaced: list[protocols.ProgramNotice | None] = []
        found: bool = False
        for notice in reversed(list(notices)):
            if found:
                replaced.insert(0, notice)

            elif self.matcher(notice):
                found = True
                replaced.insert(0, self.change(notice))

            else:
                replaced.insert(0, notice)

        if not found:
            if self.must_exist:
                raise MissingNotices(line_number=notices.line_number, location=notices.location)
            replaced.append(self.change(notices.generate_notice(msg="")))

        # mypy is silly and the overload on set_notices means the bool needs to be manually split
        if self.allow_empty:
            return notices.set_notices(replaced, allow_empty=True)
        else:
            return notices.set_notices(replaced, allow_empty=False)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyLine:
    """
    Used to modify a line notices at a specific line in a file notices.

    .. code-block:: python

        from pytest_typing_runner import notice_changers, protocols


        file_notices: protocols.FileNotices = ...
        assert file_notices.notices_at_line(5) is None

        changer = notice_changers.ModifyLine(
            name_or_line=5,
            change=lambda line_notices: line_notices.set_notices([_new_notice1, _new_notice2])
        )

        changed = changer(file_notices)
        assert list(changed.notices_at_line(5) or []) == [_new_notice1, _new_notice2]

    This also works with named lines:

    .. code-block:: python

        from pytest_typing_runner import notice_changers, protocols


        file_notices: protocols.FileNotices = ...
        file_notices = file_notices.set_name("one", 5)
        assert file_notices.notices_at_line(5) is None

        changer = notice_changers.ModifyLine(
            name_or_line="one",
            change=lambda line_notices: line_notices.set_notices([_new_notice1, _new_notice2])
        )

        changed = changer(file_notices)
        assert list(changed.notices_at_line(5) or []) == [_new_notice1, _new_notice2]

    :param name_or_line:
        Either a string used as a name, or an integer representing the specific
        line.
    :param name_must_exist:
        Defaults to ``True``. Will raise :class:`MissingNotices` if ``True``
        and ``name_or_line`` is a string that isn't registered on the file notices.
    :param line_must_exist:
        Defaults to ``True``. Will raise :class:`MissingNotices` if ``True``
        and the resolved line number from ``name_or_line`` doesn't have an
        existing line notices.
    :param change:
        A function given a line notices to return a new line notices to give to
        the file notices. If this function returns None then the file notices
        will be told to not have notices for the resolved line number. If the
        ``name_must_exist`` and ``line_must_exist`` flags are ``False`` and
        the resolved line number doesn't have an existing line notices, a new
        one will be generated to pass into ``change``

    .. automethod:: __call__
    """

    name_or_line: str | int
    name_must_exist: bool = True
    line_must_exist: bool = True
    change: protocols.LineNoticesChanger

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        """
        Perform the transformation

        :param notices: The file notices to change
        :raises MissingNotices:
            if ``name_must_exist`` is ``True`` and ``name_or_line`` is a string and
            not a registered name
        :raises MissingNotices:
            if ``line_must_exist`` is ``True`` and the resolved line number doesn't
            already have line notices on the file notices.
        :returns:
            A copy of the file notices with changed line notices for the resolved
            line number.
        """
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
        return notices.set_lines(change)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModifyFile:
    """
    Used to modify the notices for a particular location on a program notices.

    .. code-block:: python

        from pytest_typing_runner import notice_changers, protocols
        import pathlib


        location = pathlib.Path(...)

        program_notices: protocols.ProgramNotices = ...
        assert list(program_notices.notices_at_location(location) or []) == [
            _existing_line_1_notice,
            _existing_line_2_notice,
        ]

        changer = notice_changers.ModifyFile(
            location=location,
            change=lambda file_notices: file_notices.set_lines(
                {
                    5: file_notices.generate_notices_for_line(5).set_notices([_new_line_5_notice])
                }
            )
        )

        changed = changer(program_notices)
        assert list(program_notices.notices_at_location(location) or []) == [
            _existing_line_1_notice,
            _existing_line_2_notice,
            _new_line_5_notice,
        ]

    :param location: The location to modify
    :param must_exist:
        Defaults to ``True``. When ``True`` and the ``location`` isn't already in
        the program notices a :class:`MissingNotices` will be raised.
    :param change:
        A function that takes a file notices to change. One will be generated
        if the location isn't already in the program notices and ``must_exist``
        is ``False``.

    .. automethod:: __call__
    """

    location: pathlib.Path
    must_exist: bool = True
    change: protocols.FileNoticesChanger

    def __call__(self, notices: protocols.ProgramNotices) -> protocols.ProgramNotices:
        """
        Perform the transformation

        :param notices: The program notices to change
        :raises MissingNotices:
            if ``must_exist`` is ``True`` and the ``location`` isn't already in the
            program notices.
        :returns:
            A copy of the program notices with changed file notices for the specified
            location.
        """
        file_notices = notices.notices_at_location(self.location)
        if file_notices is None and self.must_exist:
            raise MissingNotices(location=self.location)

        if file_notices is None:
            file_notices = notices.generate_notices_for_location(self.location)

        return notices.set_files({self.location: self.change(file_notices)})


@dataclasses.dataclass(frozen=True, kw_only=True)
class BulkAdd:
    """
    Used to bulk add notices to a program notices.

    .. code-block:: python

        from pytest_typing_runner import notice_changers, protocols
        import pathlib


        root_dir = pathlib.Path(...)

        program_notices: protocols.ProgramNotices = ...

        changer = notice_changers.BulkAdd(
            root_dir=root_dir,
            add={
                "one": {
                    1: [
                        "a note",
                        (notices.ErrorSeverity("arg-type"), "an error"),
                    ],
                    (20, "name"): [...],
                },
                "two/three": {...},
            },
        )

        program_notices = changer(program_notices)
        # and now we have program notices for:
        # location=(root_dir / "one") | line_number=1 | severity=note | msg="a note"
        # location=(root_dir / "one") | line_number=1 | severity=error(arg-type) | msg="an error"
        # location=(root_dir / "one") | line_number=20 | ...
        # location=(root_dir / "two" / "three") | ...
        #
        # And line 20 will have the name "name"

    :param root_dir: The path all locations are relative to
    :param add:
        A Mapping of path to Mapping of line number to sequence of notices.

        Where the key for the line number is either an integer or a tuple of
        ``(line_number, line_name)`` for registering that name to that line number
        in that location.

        Where the notices are either a string indicating a note severity notice
        or a tuple of ``(severity, msg)``.

    .. automethod:: __call__
    """

    root_dir: pathlib.Path
    add: Mapping[
        str,
        Mapping[
            int | tuple[int, str],
            Sequence[str | protocols.NoticeMsg | tuple[protocols.Severity, str]],
        ],
    ]

    def __call__(self, notices: protocols.ProgramNotices) -> protocols.ProgramNotices:
        """
        Add the specified notices

        :param notices: The program notices to change
        :returns:
            A copy of the program notices with additional notices.
        """
        for path, by_line in self.add.items():
            location = self.root_dir / path
            file_notices = notices.notices_at_location(
                location
            ) or notices.generate_notices_for_location(location)

            for line_and_name, ns in by_line.items():
                if isinstance(line_and_name, int):
                    line_number = line_and_name
                else:
                    line_number, name = line_and_name
                    file_notices = file_notices.set_name(name, line_number)

                line_notices = file_notices.notices_at_line(
                    line_number
                ) or file_notices.generate_notices_for_line(line_number)
                notices_for_line: list[protocols.ProgramNotice] = list(line_notices)

                if isinstance(ns, str):
                    ns = [ns]

                for n in ns:
                    if isinstance(n, tuple):
                        notices_for_line.append(
                            line_notices.generate_notice(severity=n[0], msg=n[1])
                        )
                    else:
                        notices_for_line.append(line_notices.generate_notice(msg=n))

                if notices_for_line:
                    file_notices = file_notices.set_lines(
                        {line_number: line_notices.set_notices(notices_for_line)}
                    )

            if file_notices.has_notices or file_notices.known_names:
                notices = notices.set_files({location: file_notices})

        return notices


if TYPE_CHECKING:
    _FMO: protocols.ProgramNoticeChanger = cast(FirstMatchOnly, None)
    _ATL: protocols.LineNoticesChanger = cast(AppendToLine, None)
    _MLM: protocols.LineNoticesChanger = cast(ModifyLatestMatch, None)
    _ML: protocols.FileNoticesChanger = cast(ModifyLine, None)
    _MF: protocols.ProgramNoticesChanger = cast(ModifyFile, None)
    _BA: protocols.ProgramNoticesChanger = cast(BulkAdd, None)
