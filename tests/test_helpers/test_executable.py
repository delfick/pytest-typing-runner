import argparse
import os
import pathlib
import subprocess
import sys

from pytest_typing_runner_test_driver import executable


class TestMakePythonModule:
    def test_it_provides_a_way_of_making_a_module_for_subprocess(self) -> None:
        def make_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser()
            parser.add_argument("-s", default="hi")
            return parser

        def mainline(argv: list[str], parser: argparse.ArgumentParser, out: pathlib.Path) -> None:
            args = parser.parse_args(argv)
            out.write_text(f"Found: {args.s}")

        with executable.make_python_module("blah", make_parser=make_parser, mainline=mainline) as (
            out,
            pythonpath,
        ):
            subprocess.check_output(
                [sys.executable, "-m", "blah", "-s", "stuff"],
                env={**os.environ, "PYTHONPATH": pythonpath},
            )
            assert out.read_text() == "Found: stuff"

            subprocess.check_output(
                [sys.executable, "-m", "blah"],
                env={**os.environ, "PYTHONPATH": pythonpath},
            )
            assert out.read_text() == "Found: hi"
