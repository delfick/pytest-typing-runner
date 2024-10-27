import ast
import contextlib
import dataclasses
import os
import pathlib
import runpy
import sys
import tempfile
import textwrap
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, TypeVar, cast

from typing_extensions import assert_never

from . import errors, protocols

T_Assign = TypeVar("T_Assign", ast.Assign, ast.AnnAssign)


@dataclasses.dataclass(kw_only=True)
class FileChangerException(errors.PyTestTypingRunnerException):
    """
    Parent exception for all file_changer exceptions
    """


@dataclasses.dataclass(kw_only=True)
class LocationOutOfBounds(FileChangerException):
    """
    Risen when a location is outside of a specific parent directory
    """

    root_dir: pathlib.Path
    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to be under root_dir ({self.root_dir})"


@dataclasses.dataclass(kw_only=True)
class LocationDoesNotExist(FileChangerException):
    """
    Risen when a location that should exist does not
    """

    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to exist"


@dataclasses.dataclass(kw_only=True)
class LocationIsNotDirectory(FileChangerException):
    """
    Risen when a location that should be a directory is not a directory
    """

    location: pathlib.Path

    def __str__(self) -> str:
        return f"Expected location ({self.location}) to be a directory"


@dataclasses.dataclass(frozen=True, kw_only=True)
class FileAppender:
    """
    Used to determine what to change a file to if content were to be appended:

    .. code-block:: python

        from pytest_typing_runner import file_changers


        appender = file_changers.FileAppender(
            root_dir=root_dir,
            path="path/to/file.py",
            extra_content=textwrap.dedent(
                \"\"\"
                class Other:
                    pass
                \"\"\"
            )
        )

        # Given a pytest_typing_runner.protocols.FileModifier function
        file_modification(
            path="/path/to/file.py",
            content=appender.after_append()
        )

    :param root_dir: The base location to modify
    :param path: The path relative to ``root_dir`` to look at
    :param extra_content: The extra content to add to the existing content
    """

    root_dir: pathlib.Path
    path: str
    extra_content: str

    def after_append(self, divider: str = "\n", must_exist: bool = False) -> str:
        """
        Return a string that would be the result of appending ``self.extra_content`` to
        the contents of the file that was found.

        :param divider:
            The string that goes between the existing content (if there is existing content)
            and the extra content
        :param must_exist:
            When set to True, an exception will be raised instead of pretending the file is empty
        :raises LocationOutOfBounds: if ``self.path`` relative to ``self.root_dir`` is not under that location
        :raises LocationDoesNotExist: if ``must_exist`` is True and the location doesn't exist
        :returns: the new contents for the file
        """
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
    """
    Used to copy a specific folder under ``src`` into ``root_dir``

    .. code-block:: python

        from pytest_typing_runner import file_changers


        copier = file_changers.CopyDirectory(
            root_dir=root_dir,
            src=src,
            path="folder_in_src_to_copy",
        )

        # Given a pytest_typing_runner.protocols.FileModifier function
        copier.do_copy(modify_file=file_modification)

    :param root_dir: The base location to copy files into
    :param src: The base location to look for the ``path`` to copy from
    :param path: The path relative to ``src`` to look at and relative to ``root_dir`` to copy into
    """

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
        """
        Use the file modifier to copy files into root_dir

        :param modify_file: function that changes files
        :param skip_if_destination_exists:
            when set to True this function doesn't change anything if the root_dir
            already has the directory being looked for (without checking if the content
            in that directory match the ``src``
        :param exclude:
            an optional function that takes each file that is being copied.
            Returning ``False`` from this function will result in the file not
            being copied over

        :raises LocationOutOfBounds: if ``self.path`` relative to ``self.src`` is outside of ``self.src``
        :raises LocationOutOfBounds: if ``self.path`` relative to ``self.root_dir`` is outside of ``self.root_dir``
        :raises LocationDoesNotExist: if ``self.path`` relative to ``self.src`` does not exist
        :raises LocationIsNotDirectory: if ``self.path`` relative to ``self.src`` is not a directory
        """
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
    """
    Protocol representing a ``changer`` used by :class:`PythonFileChanger`

    It takes in a node that is either ``ast.Assign`` or ``ast.AnnAssign`` and must
    return a node of the same type.

    When modifying the node it can be useful to use a match statement:

    .. code-block:: python

        from typing import assert_never
        from pytest_typing_runner import file_changers
        from typing import TYPE_CHECKING
        import ast

        def changer(
            *,
            node: file_changers.T_Assign,
            variable_name: str,
            values: dict[str, object]
        ) -> file_changers.T_Assign:
            new_value = ... # some ast.expr object

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
            _c: file_changers.PythonVariableChanger = changer

    :param node: The ast assignment node that is being looked at
    :param variable_name: The name of the variable that was being assigned
    :param values: A dictionary of all the values in the python file being changed
    """

    def __call__(
        self, *, node: T_Assign, variable_name: str, values: dict[str, object]
    ) -> T_Assign: ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class BasicPythonAssignmentChanger:
    """
    Limited helper used to create a copy of a python file with changes to specific assignments.

    .. code-block:: python

        from pytest_typing_runner import file_changers


        changer = file_changers.BasicPythonAssignmentChanger(
            root_dir=root_dir,
            path="path/to/my_code.py",
            variable_changers={"var1": ..., "var2": ...}
        )

        # Given a pytest_typing_runner.protocols.FileModifier function
        file_modification(
            path="path/to/my_code.py",
            content=changer.after_change(default_content="")
        )

    :param root_dir: The base location to look for the ``path`` in
    :param path: The path relative to ``root_dir`` to look at
    :param variable_changers:
        A mapping where keys are the names of variables that are assigned to
        in the file. And variables are of the type :protocol:`PythonVariableChanger`.

        When any ``ast.Assign`` or ``ast.AnnAssign`` are found in the python file
        those variable changes are used with the node that was found.

        This helper is useful for modifying files like a Django settings file where the
        file only has module level assignments.
    :param cwd:
        The directory to be in and add to sys.path when determining the values
        in the file
    """

    root_dir: pathlib.Path
    cwd: pathlib.Path
    path: str

    variable_changers: Mapping[str, PythonVariableChanger]

    @contextlib.contextmanager
    def _in_cwd(self) -> Iterator[None]:
        current_cwd = str(pathlib.Path.cwd())
        want_cwd = str(self.cwd)
        sys_path_before: list[str] = list(sys.path)
        try:
            os.chdir(want_cwd)
            sys.path.append(want_cwd)
            yield
        finally:
            os.chdir(current_cwd)
            sys.path.clear()
            sys.path.extend(sys_path_before)

    def after_change(self, *, default_content: str) -> str:
        """
        Returns the contents of a file after changing specific assignments.

        The method will determine what values are in the file using ``runpy.run_path`` on the file.
        And will use a ``ast.NodeTransformer`` to find and modify ast nodes in the file to determine
        what the file the would look like after changes.

        :param default_content:
            If the file does not exist, then this is the string that will
            be used to determine values and ast nodes. A temporary file will
            be made for this purpose rather than changing the destination.

        :raises LocationOutOfBounds: if ``self.path`` relative to ``self.root_dir`` is outside of ``self.root_dir``
        """
        location = (self.root_dir / self.path).resolve()
        if not location.is_relative_to(self.root_dir):
            raise LocationOutOfBounds(root_dir=self.root_dir, location=location)

        if not location.exists():
            current = textwrap.dedent(default_content)
            with tempfile.NamedTemporaryFile(dir=self.cwd, delete=False, suffix=".py") as filename:
                tmp = pathlib.Path(filename.name)
            try:
                tmp.write_text(current)
                with self._in_cwd():
                    values = runpy.run_path(str(tmp))
            finally:
                tmp.unlink(missing_ok=True)
        else:
            current = location.read_text()
            with self._in_cwd():
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
    """
    An object that satisfies :protocol:`PythonVariableChanger`

    This can be used with something like :class:`BasicPythonAssignmentChanger` to
    perform some action if a specific variable is being assigned in the file.

    :param notify:
        A function that is called with the name of the variable and the value
        for that variable that was found.
    """

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
    """
    An object that satisfies :protocol:`PythonVariableChanger`

    This can be used with something like :class:`BasicPythonAssignmentChanger` to
    change the value being assigned to a specific variable.

    :param change:
        A function that is called with the name of the variable and the value
        for that variable that was found. The ``ast.expr`` objects the function
        returns will be used as the ``elts`` in a ``ast.List`` object that replaces
        the value being assigned to that variable.
    """

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
