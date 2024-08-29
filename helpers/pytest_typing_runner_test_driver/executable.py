import argparse
import contextlib
import inspect
import pathlib
import tempfile
import textwrap
from collections.abc import Iterator
from typing import Protocol


class MakeParser(Protocol):
    __name__: str

    def __call__(self) -> argparse.ArgumentParser: ...


class Mainline(Protocol):
    __name__: str

    def __call__(
        self, *, argv: list[str], parser: argparse.ArgumentParser, out: pathlib.Path
    ) -> None: ...


@contextlib.contextmanager
def make_python_module(
    path: str, /, *, make_parser: MakeParser, mainline: Mainline
) -> Iterator[tuple[pathlib.Path, str]]:
    assert not path.startswith("/")
    if not path.endswith(".py"):
        path = f"{path}.py"

    def make_code(out: pathlib.Path) -> str:
        lines = ["import argparse", "import pathlib"]
        lines.append(textwrap.dedent(inspect.getsource(make_parser)))
        lines.append(textwrap.dedent(inspect.getsource(mainline)))
        lines.append(
            textwrap.dedent(f"""
        if __name__ == '__main__':
            import pathlib
            import sys
            parser = {make_parser.__name__}()
            {mainline.__name__}(sys.argv[1:], parser, pathlib.Path("{out}"))
        """)
        )
        return "\n".join(lines)

    with tempfile.TemporaryDirectory() as directory:
        out = pathlib.Path(directory, "out")
        code_parent = pathlib.Path(directory, "code")
        code = code_parent / path
        code.parent.mkdir(parents=True, exist_ok=True)

        d = code.parent
        while d.is_relative_to(code_parent):
            init = d / "__init__.py"
            if not init.exists():
                init.write_text("")
            d = d.parent

        code.write_text(make_code(out))
        yield out, str(code_parent)
