import ast
import dataclasses
import pathlib
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, cast

from . import protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileAppender:
    root_dir: pathlib.Path
    path: str
    extra_content: str

    def after_append(self, divider: str = "\n", must_exist: bool = False) -> str:
        # TODO: implement
        return ""


@dataclasses.dataclass(frozen=True, kw_only=True)
class CopyDirectory:
    root_dir: pathlib.Path
    src: pathlib.Path
    path: str

    def do_copy(
        self,
        modify_file: protocols.FileModifier,
        exclude: Callable[[pathlib.Path], bool],
        skip_if_exists: bool,
    ) -> None:
        # TODO: implement
        return


class PythonVariableChanger(Protocol):
    def __call__(
        self, *, node: ast.Assign, variable_name: str, values: dict[str, object]
    ) -> ast.Assign: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class PythonFileChanger:
    root_dir: pathlib.Path
    path: str

    variable_changers: dict[str, PythonVariableChanger]

    def after_change(self, *, default_content: str) -> str:
        # TODO: implement
        return ""


@dataclasses.dataclass(frozen=True, kw_only=True)
class VariableFinder:
    notify: Callable[[object], None]

    def __call__(
        self, *, node: ast.Assign, variable_name: str, values: dict[str, object]
    ) -> ast.Assign:
        # TODO: implement
        return node


@dataclasses.dataclass(frozen=True, kw_only=True)
class ListVariableChanger:
    change_list: Callable[[Sequence[object]], Sequence[ast.expr]]

    def __call__(
        self, *, node: ast.Assign, variable_name: str, values: dict[str, object]
    ) -> ast.Assign:
        # TODO: implement
        return node


if TYPE_CHECKING:
    _VF: PythonVariableChanger = cast(VariableFinder, None)
    _LVC: PythonVariableChanger = cast(ListVariableChanger, None)
