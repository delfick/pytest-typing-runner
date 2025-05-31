import ast
import dataclasses
import pathlib
import textwrap
from collections.abc import Sequence

import pytest
from typing_extensions import assert_never

from pytest_typing_runner import file_changers


class TestFileAppender:
    def test_it_can_return_content_with_appended_content(self, tmp_path: pathlib.Path) -> None:
        appender = file_changers.FileAppender(
            root_dir=tmp_path, path="somewhere/nice", extra_content="extra"
        )

        location = tmp_path / appender.path
        location.parent.mkdir(parents=True)
        original_content = "hello\nthere"
        location.write_text(original_content)

        assert appender.after_append() == "hello\nthere\nextra"
        assert location.read_text() == original_content

        assert appender.after_append(divider="..") == "hello\nthere..extra"
        assert location.read_text() == original_content

    def test_it_complains_if_accessing_file_outside_root_dir(self, tmp_path: pathlib.Path) -> None:
        directory_one = tmp_path / "one"
        directory_one.mkdir()

        directory_two = tmp_path / "root_file_system"
        directory_two.mkdir()

        appender = file_changers.FileAppender(
            root_dir=directory_one,
            path=str((directory_two / "fstab").resolve()),
            extra_content="something dangerous",
        )

        with pytest.raises(file_changers.LocationOutOfBounds) as e:
            appender.after_append()

        assert e.value.root_dir == directory_one
        assert e.value.location == directory_two / "fstab"

    def test_it_can_be_told_to_complain_if_no_file_to_append_to(
        self, tmp_path: pathlib.Path
    ) -> None:
        appender = file_changers.FileAppender(
            root_dir=tmp_path,
            path="hello/there",
            extra_content="stuff",
        )

        with pytest.raises(file_changers.LocationDoesNotExist) as e:
            appender.after_append(must_exist=True)

        assert e.value.location == tmp_path / "hello" / "there"

    def test_it_can_pretend_file_not_existing_is_empty_file(self, tmp_path: pathlib.Path) -> None:
        appender = file_changers.FileAppender(
            root_dir=tmp_path,
            path="hello/there",
            extra_content="things",
        )

        assert appender.after_append() == "things"


class TestCopyDirectory:
    @pytest.fixture
    def root_dir(self, tmp_path: pathlib.Path) -> pathlib.Path:
        root_dir = tmp_path / "root"
        root_dir.mkdir()
        return root_dir

    @pytest.fixture
    def src(self, tmp_path: pathlib.Path) -> pathlib.Path:
        src = tmp_path / "src"
        src.mkdir()
        return src

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class FileModifier:
        modified: dict[str, str | None] = dataclasses.field(default_factory=dict)

        def __call__(self, *, path: str, content: str | None) -> None:
            self.modified[path] = content

    @pytest.fixture
    def modify_file(self) -> FileModifier:
        return self.FileModifier()

    def test_it_complains_if_src_does_not_exist(
        self, root_dir: pathlib.Path, src: pathlib.Path, modify_file: FileModifier
    ) -> None:
        assert not (src / "one").exists()
        copier = file_changers.CopyDirectory(root_dir=root_dir, src=src, path="one")

        with pytest.raises(file_changers.LocationDoesNotExist) as e:
            copier.do_copy(modify_file=modify_file, skip_if_destination_exists=True)

        assert e.value.location == src / "one"

    def test_it_complains_if_src_is_not_a_directory(
        self, root_dir: pathlib.Path, src: pathlib.Path, modify_file: FileModifier
    ) -> None:
        (src / "one").write_text("is_a_file")
        copier = file_changers.CopyDirectory(root_dir=root_dir, src=src, path="one")

        with pytest.raises(file_changers.LocationIsNotDirectory) as e:
            copier.do_copy(modify_file=modify_file, skip_if_destination_exists=True)

        assert e.value.location == src / "one"

    def test_it_can_skip_if_the_destination_already_exists(
        self, root_dir: pathlib.Path, src: pathlib.Path, modify_file: FileModifier
    ) -> None:
        copier = file_changers.CopyDirectory(root_dir=root_dir, src=src, path="one")

        copy_from = src / "one"
        copy_from.mkdir()
        (copy_from / "one").write_text("one content")
        (copy_from / "two").write_text("two content")
        (copy_from / "three").mkdir()
        (copy_from / "three" / "four").write_text("four content")

        (root_dir / "one").mkdir()
        (root_dir / "one" / "one").write_text("existing one content")

        copier.do_copy(modify_file=modify_file, skip_if_destination_exists=True)
        assert modify_file.modified == {}

    def test_it_can_override_the_destination_if_already_exists(
        self, root_dir: pathlib.Path, src: pathlib.Path, modify_file: FileModifier
    ) -> None:
        copier = file_changers.CopyDirectory(root_dir=root_dir, src=src, path="wanted")

        copy_from = src / "wanted"
        copy_from.mkdir()
        (copy_from / "one").write_text("one content")
        (copy_from / "two").write_text("two content")
        (copy_from / "three").mkdir()
        (copy_from / "three" / "four").write_text("four content")

        (root_dir / "wanted").mkdir()
        (root_dir / "wanted" / "one").write_text("existing one content")

        copier.do_copy(modify_file=modify_file, skip_if_destination_exists=False)
        assert modify_file.modified == {
            "wanted/one": "one content",
            "wanted/two": "two content",
            "wanted/three/four": "four content",
        }

    def test_it_can_be_given_an_exclude_filter(
        self, root_dir: pathlib.Path, src: pathlib.Path, modify_file: FileModifier
    ) -> None:
        copier = file_changers.CopyDirectory(root_dir=root_dir, src=src, path="wanted")

        copy_from = src / "wanted"
        copy_from.mkdir()
        (copy_from / "one").write_text("one content")
        (copy_from / "two.pyc").write_text("two content")
        (copy_from / "three").mkdir()
        (copy_from / "three" / "four").write_text("four content")

        (root_dir / "wanted").mkdir()
        (root_dir / "wanted" / "one").write_text("existing one content")

        # without exclude
        copier.do_copy(modify_file=modify_file, skip_if_destination_exists=False)
        assert modify_file.modified == {
            "wanted/one": "one content",
            "wanted/two.pyc": "two content",
            "wanted/three/four": "four content",
        }

        modify_file.modified.clear()

        # vs with exclude
        copier.do_copy(
            modify_file=modify_file,
            skip_if_destination_exists=False,
            exclude=lambda l: l.suffix == ".pyc",
        )
        assert modify_file.modified == {
            "wanted/one": "one content",
            "wanted/three/four": "four content",
        }


class TestBasicPythonAssignmentChanger:
    def test_it_complains_if_location_is_outside_root_dir(self, tmp_path: pathlib.Path) -> None:
        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=tmp_path, root_dir=tmp_path, path="../../somewhere", variable_changers={}
        )

        with pytest.raises(file_changers.LocationOutOfBounds) as e:
            changer.after_change(default_content="")

        assert e.value.location == (tmp_path / ".." / ".." / "somewhere").resolve()

    def test_it_uses_default_content_if_file_doesnt_exist(self, tmp_path: pathlib.Path) -> None:
        default_content = """
        ONE: int = 1
        TWO: list[str] = [i for i in range(10)]
        THREE = 'asdf'
        FOUR = 2
        """

        called: list[tuple[str, object]] = []

        def looker(
            *, node: file_changers.T_Assign, variable_name: str, values: dict[str, object]
        ) -> file_changers.T_Assign:
            called.append((variable_name, values[variable_name]))
            return node

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=tmp_path,
            root_dir=tmp_path,
            path="my_file.py",
            variable_changers={"ONE": looker, "TWO": looker, "THREE": looker},
        )
        assert (
            changer.after_change(default_content=default_content).strip()
            == textwrap.dedent(default_content).strip()
        )
        assert called == [("ONE", 1), ("TWO", list(range(10))), ("THREE", "asdf")]

    def test_it_modify_the_nodes(self, tmp_path: pathlib.Path) -> None:
        default_content = """
        ONE: int = 1
        TWO: list[str] = [i for i in range(10)]
        THREE = 'asdf'
        FOUR = 2
        """

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Change:
            new_value: ast.expr

            def __call__(
                self,
                *,
                node: file_changers.T_Assign,
                variable_name: str,
                values: dict[str, object],
            ) -> file_changers.T_Assign:
                match node:
                    case ast.AnnAssign(target=target, annotation=annotation, simple=simple):
                        return ast.AnnAssign(
                            target=target,
                            annotation=annotation,
                            simple=simple,
                            value=self.new_value,
                        )
                    case ast.Assign(targets=targets):
                        return ast.Assign(targets=targets, value=self.new_value)
                    case _:
                        assert_never(node)

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=tmp_path,
            root_dir=tmp_path,
            path="my_file.py",
            variable_changers={
                "ONE": Change(new_value=ast.Constant(3)),
                "TWO": Change(new_value=ast.List(elts=[ast.Constant(4), ast.Constant(5)])),
                "THREE": Change(new_value=ast.Constant("trees")),
            },
        )

        expected = textwrap.dedent("""
        ONE: int = 3
        TWO: list[str] = [4, 5]
        THREE = 'trees'
        FOUR = 2
        """)

        assert changer.after_change(default_content=default_content).strip() == expected.strip()

    def test_it_can_rely_on_being_in_cwd(self, tmp_path: pathlib.Path) -> None:
        default_content = """
        import pathlib
        ONE: str = pathlib.Path('blah').read_text()
        """

        cwd = tmp_path / "configs"
        cwd.mkdir()

        (cwd / "blah").write_text("hi")

        called: list[tuple[str, object]] = []

        def looker(
            *, node: file_changers.T_Assign, variable_name: str, values: dict[str, object]
        ) -> file_changers.T_Assign:
            called.append((variable_name, values[variable_name]))
            return node

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=cwd,
            root_dir=tmp_path,
            path="configs/my_file.py",
            variable_changers={"ONE": looker},
        )
        got = changer.after_change(default_content=default_content).strip()
        assert got == textwrap.dedent(default_content).strip()
        assert called == [("ONE", "hi")]

        (cwd / "my_file.py").write_text(got)
        (cwd / "blah").write_text("there")

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=cwd,
            root_dir=tmp_path,
            path="configs/my_file.py",
            variable_changers={"ONE": looker},
        )
        got = changer.after_change(default_content="empty_and_not_used").strip()
        assert got == textwrap.dedent(default_content).strip()
        assert called == [("ONE", "hi"), ("ONE", "there")]


class TestVariableFinder:
    def test_it_allows_being_notified_of_some_variable(self, tmp_path: pathlib.Path) -> None:
        original = textwrap.dedent("""
        ONE: int = 1
        TWO = 2
        THREE = 3
        FOUR: list[int] = list(range(10))
        """)

        (tmp_path / "my_file.py").write_text(original)

        called: list[tuple[str, object]] = []

        def notifier(*, variable_name: str, value: object) -> None:
            called.append((variable_name, value))

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=tmp_path,
            root_dir=tmp_path,
            path="my_file.py",
            variable_changers={
                "ONE": file_changers.VariableFinder(notify=notifier),
                "THREE": file_changers.VariableFinder(notify=notifier),
                "FOUR": file_changers.VariableFinder(notify=notifier),
                "FIVE": file_changers.VariableFinder(notify=notifier),
            },
        )

        assert changer.after_change(default_content="").strip() == original.strip()
        assert called == [("ONE", 1), ("THREE", 3), ("FOUR", list(range(10)))]


class TestListVariableChanger:
    def test_it_calls_provided_function_with_found_list_or_empty_list(
        self, tmp_path: pathlib.Path
    ) -> None:
        original = textwrap.dedent("""
        ONE = 3
        TWO: list[int] = list(range(10))
        OTHER: str = 'asdf'
        OTHER2 = True
        """)

        (tmp_path / "my_file.py").write_text(original)

        called: list[tuple[str, Sequence[object]]] = []

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Change:
            new_values: list[int]

            def __call__(
                self, *, variable_name: str, values: Sequence[object]
            ) -> Sequence[ast.expr]:
                called.append((variable_name, values))
                return [ast.Constant(i) for i in self.new_values]

        changer = file_changers.BasicPythonAssignmentChanger(
            cwd=tmp_path,
            root_dir=tmp_path,
            path="my_file.py",
            variable_changers={
                "ONE": file_changers.ListVariableChanger(change=Change(new_values=[1, 2])),
                "TWO": file_changers.ListVariableChanger(change=Change(new_values=[3, 4])),
                "THREE": file_changers.ListVariableChanger(change=Change(new_values=[5, 6])),
            },
        )

        expected = textwrap.dedent("""
        ONE = [1, 2]
        TWO: list[int] = [3, 4]
        OTHER: str = 'asdf'
        OTHER2 = True
        """)

        got = changer.after_change(default_content="")
        assert called == [("ONE", []), ("TWO", list(range(10)))]
        assert got.strip() == expected.strip()
