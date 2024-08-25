from collections.abc import MutableSequence, Sequence
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
    def line_number_for_name_adjustment(self) -> int:
        """
        The amount to adjust the ``line_number_for_name`` line. This is used
        before the next comment parser is used
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

    def __call__(self, before: ParsedLineBefore, /) -> ParsedLineAfter: ...


class ModifyParsedLineBefore(Protocol):
    """
    Used to modify the lines that came before the comment match

    Must return the amount to move the ``line_number_for_name``
    """

    def __call__(self, *, before: ParsedLineBefore) -> int: ...


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
    def severity(self) -> protocols.Severity:
        """
        The ``severity`` to use if this match adds a notice
        """

    @property
    def msg(self) -> str:
        """
        The ``msg`` to use if this match adds a notice
        """

    @property
    def modify_lines(self) -> ModifyParsedLineBefore | None:
        """
        Used to modify the lines if changes to the file are required
        """


class CommentMatchMaker(Protocol):
    def __call__(self, line: str, /) -> CommentMatch | None: ...


if TYPE_CHECKING:
    P_ParsedLineBefore = ParsedLineBefore
    P_ParsedLineAfter = ParsedLineAfter
    P_LineParser = LineParser
    P_ModifyParsedLineBefore = ModifyParsedLineBefore
    P_CommentMatch = CommentMatch
    P_CommentMatchMaker = CommentMatchMaker