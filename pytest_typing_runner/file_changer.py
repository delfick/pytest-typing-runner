import ast
import dataclasses
import os
import pathlib
import runpy
import tempfile
import textwrap
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol, TypeVar, cast

from typing_extensions import assert_never

from . import errors, protocols

T_Assign = TypeVar("T_Assign", ast.Assign, ast.AnnAssign)


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileChangerException(errors.PyTestTypingRunnerException):
    pass


@dataclasses.dataclass(frozen=True, kw_only=True)
class LocationOutOfBounds(FileChangerException):
    root_dir: pathlib.Path
    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to be under root_dir ({self.root_dir})"


@dataclasses.dataclass(frozen=True, kw_only=True)
class LocationDoesNotExist(FileChangerException):
    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to exist"


@dataclasses.dataclass(frozen=True, kw_only=True)
class LocationIsNotDirectory(FileChangerException):
    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to be a directory"


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileAppender:
    root_dir: pathlib.Path
    path: str
    extra_content: str

    def after_append(self, divider: str = "\n", must_exist: bool = False) -> str:
        content: list[str]
        location = (self.root_dir / self.path).resolve()
        if not location.is_relative_to(self.root_dir):
            raise LocationOutOfBounds(root_dir=self.root_dir, location=location)
        if location.exists():
            content = [location.read_text()]
        else:
            if must_exist:
                raise LocationDoesNotExist(location=location)
            content = []

        return divider.join([*content, textwrap.dedent(self.extra_content)])


@dataclasses.dataclass(frozen=True, kw_only=True)
class CopyDirectory:
    root_dir: pathlib.Path
    src: pathlib.Path
    path: str

    def do_copy(
        self,
        *,
        modify_file: protocols.FileModifier,
        skip_if_destination_exists: bool,
        exclude: Callable[[pathlib.Path], bool] | None = None,
    ) -> None:
        copy_from = (self.src / self.path).resolve()
        if not copy_from.is_relative_to(self.src):
            raise LocationOutOfBounds(root_dir=self.src, location=copy_from)

        if not copy_from.exists():
            raise LocationDoesNotExist(location=copy_from)

        if not copy_from.is_dir():
            raise LocationIsNotDirectory(location=copy_from)

        destination = (self.root_dir / self.path).resolve()
        if not destination.is_relative_to(self.root_dir):
            raise LocationOutOfBounds(root_dir=self.root_dir, location=destination)

        if skip_if_destination_exists and destination.exists():
            return

        for root, _, files in os.walk(copy_from):
            for name in files:
                location = pathlib.Path(root, name)
                if exclude is not None and exclude(location):
                    continue

                modify_file(
                    path=str(location.relative_to(self.src)),
                    content=location.read_text(),
                )


class PythonVariableChanger(Protocol):
    def __call__(
        self, *, node: T_Assign, variable_name: str, values: dict[str, object]
    ) -> T_Assign: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class PythonFileChanger:
    root_dir: pathlib.Path
    path: str

    variable_changers: dict[str, PythonVariableChanger]

    def after_change(self, *, default_content: str) -> str:
        location = (self.root_dir / self.path).resolve()
        if not location.is_relative_to(self.root_dir):
            raise LocationOutOfBounds(root_dir=self.root_dir, location=location)

        if not location.exists():
            current = textwrap.dedent(default_content)
            with tempfile.TemporaryDirectory() as directory:
                tmp = pathlib.Path(directory) / "tmp.py"
                tmp.write_text(current)
                values = runpy.run_path(str(tmp))
        else:
            current = location.read_text()
            values = runpy.run_path(str(location))

        parsed = ast.parse(current)
        variable_changers = self.variable_changers

        class Fixer(ast.NodeTransformer):
            def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
                match node.target:
                    case ast.Name(id=variable_name):
                        changer = variable_changers.get(variable_name)
                        if changer is None:
                            return node
                        else:
                            return changer(node=node, variable_name=variable_name, values=values)
                    case _:
                        return node

            def visit_Assign(self, node: ast.Assign) -> ast.Assign:
                match node.targets:
                    case [ast.Name(id=variable_name)]:
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
    class Notifier(Protocol):
        def __call__(self, *, variable_name: str, value: object) -> None: ...

    notify: Notifier

    def __call__(
        self, *, node: T_Assign, variable_name: str, values: dict[str, object]
    ) -> T_Assign:
        self.notify(variable_name=variable_name, value=values[variable_name])
        return node


@dataclasses.dataclass(frozen=True, kw_only=True)
class ListVariableChanger:
    class Changer(Protocol):
        def __call__(
            self, *, variable_name: str, values: Sequence[object]
        ) -> Sequence[ast.expr]: ...

    change: Changer

    def __call__(
        self, *, node: T_Assign, variable_name: str, values: dict[str, object]
    ) -> T_Assign:
        current: list[object] = []
        if isinstance(found := values[variable_name], list):
            current = found

        if not isinstance(current, list):
            current = []

        changed = self.change(variable_name=variable_name, values=current)
        new_value = ast.List(elts=list(changed))

        match node:
            case ast.AnnAssign(target=target, annotation=annotation, simple=simple):
                return ast.AnnAssign(
                    target=target, annotation=annotation, simple=simple, value=new_value
                )
            case ast.Assign(targets=targets):
                return ast.Assign(targets=targets, value=new_value)
            case _:
                assert_never(node)


if TYPE_CHECKING:
    _VF: PythonVariableChanger = cast(VariableFinder, None)
    _LVC: PythonVariableChanger = cast(ListVariableChanger, None)
