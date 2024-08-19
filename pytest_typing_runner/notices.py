import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from . import protocols


def parse_notices_from_file(notices: protocols.FileNotices) -> protocols.FileNotices:
    # TODO: implement
    return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class RevealedType:
    name: str
    revealed: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        # TODO: implement
        return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class Error:
    name: str
    error: str
    error_type: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        # TODO: implement
        return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class SetErrors:
    name: str
    errors: Mapping[str, str]

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        # TODO: implement
        return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class Note:
    name: str
    note: str
    append: bool

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        # TODO: implement
        return notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class RemoveFromRevealedType:
    name: str
    remove: str

    def __call__(self, notices: protocols.FileNotices) -> protocols.FileNotices:
        # TODO: implement
        return notices


if TYPE_CHECKING:
    _E: protocols.FileNoticesChanger = cast(Error, None)
    _N: protocols.FileNoticesChanger = cast(Note, None)
    _RT: protocols.FileNoticesChanger = cast(RevealedType, None)
