import ast
import dataclasses
import os
import pathlib
import runpy
import textwrap
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, cast

from . import protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileAppender:
    root_dir: pathlib.Path
    path: str
    extra_content: str

    def after_append(self, divider: str = "\n", must_exist: bool = False) -> str:
        content: list[str]
        location = self.root_dir / self.path
        if location.exists():
            content = [location.read_text()]
        else:
            if must_exist:
                raise AssertionError(f"Expected {location} to already exist")
            content = []

        return divider.join([*content, textwrap.dedent(self.extra_content)])


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
        if not self.src.exists():
            return

        if not self.src.is_dir():
            return

        if skip_if_exists:
            if (self.root_dir / self.path).exists():
                return

        for root, _, files in os.walk(self.src):
            for name in files:
                location = pathlib.Path(root, name)
                if exclude(location):
                    continue

                path = pathlib.Path(self.path, location.relative_to(self.src))
                modify_file(path=str(path), content=location.read_text())


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
        location = self.root_dir / self.path
        if not location.exists():
            location.write_text(default_content)

        current = location.read_text()

        values = runpy.run_path(str(location))
        parsed = ast.parse(current)
        variable_changers = self.variable_changers

        found: set[str] = set()

        class Fixer(ast.NodeTransformer):
            def visit_Assign(self, node: ast.Assign) -> ast.Assign:
                match node.targets:
                    case [ast.Name(id=variable_name)]:
                        found.add(variable_name)
                        changer = variable_changers.get(variable_name)
                        if changer is None:
                            return node
                        else:
                            return changer(node=node, variable_name=variable_name, values=values)
                    case _:
                        return node

        Fixer().visit(parsed)
        return ast.unparse(ast.fix_missing_locations(parsed))


@dataclasses.dataclass(frozen=True, kw_only=True)
class VariableFinder:
    notify: Callable[[object], None]

    def __call__(
        self, *, node: ast.Assign, variable_name: str, values: dict[str, object]
    ) -> ast.Assign:
        self.notify(values[variable_name])
        return node


@dataclasses.dataclass(frozen=True, kw_only=True)
class ListVariableChanger:
    change_list: Callable[[Sequence[object]], Sequence[ast.expr]]

    def __call__(
        self, *, node: ast.Assign, variable_name: str, values: dict[str, object]
    ) -> ast.Assign:
        current: list[object] = []
        if isinstance(node.value, ast.List):
            if isinstance(found := values[variable_name], list):
                current = found

        if not isinstance(current, list):
            current = []

        changed = self.change_list(current)
        return ast.Assign(targets=node.targets, value=ast.List(elts=list(changed)))


if TYPE_CHECKING:
    _VF: PythonVariableChanger = cast(VariableFinder, None)
    _LVC: PythonVariableChanger = cast(ListVariableChanger, None)
