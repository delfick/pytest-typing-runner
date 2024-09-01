from collections.abc import Iterator, MutableSequence, Sequence
from typing import TYPE_CHECKING, Protocol

from .. import protocols


class ParsedLineBefore(Protocol):
    """
    Represents the lines that came before
    """

    @property
    def lines(self) -> MutableSequence[str]:
        """
        The lines that came before this line including the line being matched
        """

    @property
    def line_number_for_name(self) -> int:
        """
        The line number that represents the line being given a name
        """


class ModifyParsedLineBefore(Protocol):
    """
    Used to modify the lines that came before the comment match

    If it yields no lines, then no changes are made.

    If it does yield lines then the line at ``line_number_for_line`` are replaced
    with the lines that were iterated.
    """

    def __call__(self, *, before: ParsedLineBefore) -> Iterator[str]: ...


class ParsedLineAfter(Protocol):
    """
    The changes to make to a line after all comments have been parsed
    """

    @property
    def names(self) -> Sequence[str]:
        """
        Any names to give to the ``line_number_for_name``
        """

    @property
    def notice_changers(self) -> Sequence[protocols.LineNoticesChanger]:
        """
        Any changers for the notices on the ``line_number_for_name`` line

        These are called after all processing of the line is complete
        """

    @property
    def modify_lines(self) -> ModifyParsedLineBefore | None:
        """
        Function to modify the line at ``line_number_for_name``
        """

    @property
    def real_line(self) -> bool:
        """
        Indicates if this is a real line

        When False, the ``line_number_for_name`` will not be progressed after
        the line is fully processed
        """


class LineParser(Protocol):
    """
    Function that takes a line and returns instructions for change to
    the lines or to the notices
    """

    def __call__(
        self,
        before: ParsedLineBefore,
        /,
        *,
        msg_maker_map: protocols.NoticeMsgMakerMap | None = None,
    ) -> ParsedLineAfter: ...


class CommentMatch(Protocol):
    @property
    def names(self) -> Sequence[str]:
        """
        Any names to given the ``line_number_for_name`` after the line is fully
        processed.
        """

    @property
    def is_note(self) -> bool:
        """
        Whether this match adds a note
        """

    @property
    def is_reveal(self) -> bool:
        """
        Whether this match adds a type reveal
        """

    @property
    def is_error(self) -> bool:
        """
        Whether this match adds an error
        """

    @property
    def is_warning(self) -> bool:
        """
        Whether this match adds a warning
        """

    @property
    def is_whole_line(self) -> bool:
        """
        Whether this match is for the whole line
        """

    @property
    def severity(self) -> protocols.Severity:
        """
        The ``severity`` to use if this match adds a notice
        """

    @property
    def msg(self) -> str | protocols.NoticeMsg:
        """
        The ``msg`` to use if this match adds a notice
        """

    @property
    def modify_lines(self) -> ModifyParsedLineBefore | None:
        """
        Used to modify the lines if changes to the file are required
        """


class CommentMatchMaker(Protocol):
    def __call__(
        self, line: str, /, *, msg_maker_map: protocols.NoticeMsgMakerMap | None = None
    ) -> Iterator[CommentMatch]: ...


if TYPE_CHECKING:
    P_ParsedLineBefore = ParsedLineBefore
    P_ParsedLineAfter = ParsedLineAfter
    P_LineParser = LineParser
    P_ModifyParsedLineBefore = ModifyParsedLineBefore
    P_CommentMatch = CommentMatch
    P_CommentMatchMaker = CommentMatchMaker
