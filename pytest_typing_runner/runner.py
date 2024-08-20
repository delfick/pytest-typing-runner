import contextlib
import dataclasses
import importlib
import io
import os
import pathlib
import subprocess
import sys
from collections.abc import Iterator, MutableMapping, MutableSequence, Sequence
from typing import TYPE_CHECKING, Generic, TextIO, cast

import pytest

from . import expectations, output, protocols


@dataclasses.dataclass(kw_only=True)
class RunOptions(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunOptions
    """

    scenario: protocols.T_Scenario
    typing_strategy: protocols.Strategy
    runner: protocols.ProgramRunner[protocols.T_Scenario]
    cwd: pathlib.Path
    args: MutableSequence[str]
    check_paths: MutableSequence[str]
    do_followup: bool
    environment_overrides: MutableMapping[str, str | None]


class ExternalMypyRunner(Generic[protocols.T_Scenario]):
    def __init__(self, *, mypy_name: str = "mypy") -> None:
        self._command: Sequence[str] = (sys.executable, "-m", mypy_name)

    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> expectations.RunResult[protocols.T_Scenario]:
        """
        Run mypy as an external process
        """
        env = dict(os.environ)
        for k, v in options.environment_overrides.items():
            if v is None:
                if k in env:
                    del env[k]
            else:
                env[k] = v

        completed = subprocess.run(
            [*self._command, *options.args, *options.check_paths],
            capture_output=True,
            cwd=options.cwd,
            env=env,
        )
        return expectations.RunResult.from_options(
            options,
            completed.returncode,
            stdout=completed.stdout.decode(),
            stderr=completed.stderr.decode(),
        )

    def check_notices(
        self,
        *,
        result: protocols.RunResult[protocols.T_Scenario],
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        lines: list[str] = result.stdout.strip().split("\n")
        if lines[-1].startswith("Found "):
            lines.pop()

        if lines[-1].startswith("Success: no issues"):
            lines.pop()

        notices = output.interpret_mypy_output(result.options.scenario, result.options, lines)
        output.compare_notices(
            notices.diff(root_dir=result.options.scenario.root_dir, other=expected_notices)
        )

    def short_display(self) -> str:
        return " ".join(self._command)


class SameProcessMypyRunner(Generic[protocols.T_Scenario]):
    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.RunResult[protocols.T_Scenario]:
        """
        Run mypy inside the existing process
        """

        @contextlib.contextmanager
        def saved_sys() -> Iterator[None]:
            previous_path = list(sys.path)
            previous_modules = sys.modules.copy()
            try:
                yield
            finally:
                sys.path = previous_path
                sys.modules = previous_modules

        exit_code = -1
        with saved_sys(), pytest.MonkeyPatch().context() as monkey_patch:
            for k, v in options.environment_overrides.items():
                if v is None:
                    monkey_patch.delenv(k, raising=False)
                else:
                    monkey_patch.setenv(k, v)

            if (cwd_str := str(options.cwd)) not in sys.path:
                sys.path.insert(0, cwd_str)

            stdout = io.StringIO()
            stderr = io.StringIO()

            with stdout, stderr:
                exit_code = self._run_inprocess(options, stdout=stdout, stderr=stderr)

            return expectations.RunResult.from_options(
                options, exit_code, stdout=stdout.getvalue(), stderr=stderr.getvalue()
            )

    def _run_inprocess(
        self, options: protocols.RunOptions[protocols.T_Scenario], stdout: TextIO, stderr: TextIO
    ) -> int:
        from mypy import build
        from mypy.fscache import FileSystemCache
        from mypy.main import process_options

        fscache = FileSystemCache()
        mypy_sources, mypy_options = process_options(
            list([*options.args, *options.check_paths]), fscache=fscache
        )

        error_messages: list[str] = []

        def flush_errors(filename: str | None, new_messages: list[str], is_serious: bool) -> None:
            error_messages.extend(new_messages)
            f = stderr if is_serious else stdout
            try:
                for msg in new_messages:
                    f.write(msg + "\n")
                f.flush()
            except BrokenPipeError:
                sys.exit(2)

        if importlib.metadata.version("mypy") < "1.8.0":
            new_flush_errors = flush_errors

            def flush_errors(new_messages: list[str], is_serious: bool) -> None:  # type: ignore[misc]
                return new_flush_errors(None, new_messages, is_serious)

        try:
            build.build(
                mypy_sources,
                mypy_options,
                flush_errors=flush_errors,
                fscache=fscache,
                stdout=stdout,
                stderr=stderr,
            )

        except SystemExit as sysexit:
            # The code to a SystemExit is optional
            # From python docs, if the code is None then the exit code is 0
            # Otherwise if the code is not an integer the exit code is 1
            code = sysexit.code
            if code is None:
                code = 0
            elif not isinstance(code, int):
                code = 1

            return code
        finally:
            fscache.flush()

        if error_messages:
            return 1
        else:
            return 0

    def check_notices(
        self,
        *,
        result: protocols.RunResult[protocols.T_Scenario],
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        lines: list[str] = result.stdout.strip().split("\n")
        if lines[-1].startswith("Found "):
            lines.pop()

        if lines[-1].startswith("Success: no issues"):
            lines.pop()

        notices = output.interpret_mypy_output(result.options.scenario, result.options, lines)
        output.compare_notices(
            notices.diff(root_dir=result.options.scenario.root_dir, other=expected_notices)
        )

    def short_display(self) -> str:
        return "inprocess::mypy"


class ExternalDaemonMypyRunner(ExternalMypyRunner[protocols.T_Scenario]):
    def __init__(self) -> None:
        super().__init__(mypy_name="mypy.dmypy")

    def run(
        self, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> expectations.RunResult[protocols.T_Scenario]:
        """
        Run dmypy as an external process
        """
        result = super().run(options)
        lines = result.stdout.strip().split("\n")
        if lines and lines[-1].startswith("Success: no issues found"):
            # dmypy can return exit_code=1 even if it was successful
            return dataclasses.replace(result, exit_code=0)
        else:
            return result

    def check_notices(
        self,
        *,
        result: protocols.RunResult[protocols.T_Scenario],
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        lines: list[str] = result.stdout.strip().split("\n")
        if lines[-1].startswith("Found "):
            lines.pop()

        elif lines[-1].startswith("Success: no issues"):
            lines.pop()

        daemon_restarted: bool = False
        if (
            len(lines) > 2
            and lines[0] == "Restarting: plugins changed"
            and lines[1] == "Daemon stopped"
        ):
            lines.pop(0)
            lines.pop(0)
            daemon_restarted = True

        if lines and lines[0] == "Daemon started":
            lines.pop(0)

        notices = output.interpret_mypy_output(result.options.scenario, result.options, lines)
        output.compare_notices(
            notices.diff(root_dir=result.options.scenario.root_dir, other=expected_notices)
        )
        self.check_daemon_restarted(result, restarted=daemon_restarted)

    def check_daemon_restarted(
        self,
        result: protocols.RunResult[protocols.T_Scenario],
        *,
        restarted: bool,
    ) -> None:
        if result.options.scenario.expect_dmypy_restarted:
            # Followup run should not restart the daemon again
            result.options.scenario.expect_dmypy_restarted = False

            # We expected a restart, assert we did actually restart
            assert restarted
        else:
            assert not restarted

    def short_display(self) -> str:
        return " ".join(self._command)


if TYPE_CHECKING:
    _RO: protocols.RunOptions[protocols.P_Scenario] = cast(RunOptions[protocols.P_Scenario], None)

    _EMR: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        ExternalMypyRunner[protocols.P_Scenario], None
    )
    _SPM: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        SameProcessMypyRunner[protocols.P_Scenario], None
    )
    _EDMR: protocols.ProgramRunner[protocols.P_Scenario] = cast(
        ExternalDaemonMypyRunner[protocols.P_Scenario], None
    )
