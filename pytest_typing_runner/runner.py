import contextlib
import dataclasses
import functools
import importlib
import io
import os
import pathlib
import subprocess
import sys
from collections.abc import Iterator, MutableMapping, MutableSequence, Sequence
from typing import TYPE_CHECKING, ClassVar, Generic, TextIO, cast

import pytest

from . import expectations, parse, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunOptions(Generic[protocols.T_Scenario]):
    """
    A concrete implementation of protocols.RunOptions
    """

    scenario_runner: protocols.ScenarioRunner[protocols.T_Scenario]
    make_program_runner: protocols.ProgramRunnerMaker[protocols.T_Scenario]
    cwd: pathlib.Path
    args: MutableSequence[str]
    check_paths: MutableSequence[str]
    do_followup: bool
    environment_overrides: MutableMapping[str, str | None]
    cleaners: protocols.RunCleaners


@dataclasses.dataclass(frozen=True, kw_only=True)
class MypyChecker(Generic[protocols.T_Scenario]):
    result: expectations.RunResult
    runner: protocols.ProgramRunner[protocols.T_Scenario]

    def _check_lines(self, lines: list[str], expected_notices: protocols.ProgramNotices) -> None:
        got = parse.MypyOutput.parse(
            lines,
            into=self.runner.options.scenario_runner.generate_program_notices(),
            normalise=functools.partial(
                self.runner.options.scenario_runner.normalise_program_runner_notice,
                self.runner.options,
            ),
            root_dir=self.runner.options.cwd,
        )
        expectations.compare_notices(
            got.diff(root_dir=self.runner.options.cwd, other=expected_notices)
        )

    def check(self, expected_notices: protocols.ProgramNotices, /) -> None:
        lines: list[str] = [
            line
            for line in self.result.stdout.strip().split("\n")
            if not line.startswith(":debug:")
        ]
        if lines[-1].startswith("Found "):
            lines.pop()

        if lines[-1].startswith("Success: no issues"):
            lines.pop()

        self._check_lines(lines, expected_notices)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExternalMypyRunner(Generic[protocols.T_Scenario]):
    mypy_name: ClassVar[str] = "mypy"
    options: protocols.RunOptions[protocols.T_Scenario]

    @property
    def command(self) -> Sequence[str]:
        return (sys.executable, "-m", self.mypy_name)

    def short_display(self) -> str:
        return " ".join(self.command)

    def run(
        self, *, checker_kls: type[MypyChecker[protocols.T_Scenario]] = MypyChecker
    ) -> protocols.NoticeChecker[protocols.T_Scenario]:
        """
        Run mypy as an external process
        """
        env = dict(os.environ)
        for k, v in self.options.environment_overrides.items():
            if v is None:
                if k in env:
                    del env[k]
            else:
                env[k] = v

        completed = subprocess.run(
            [*self.command, *self.options.args, *self.options.check_paths],
            capture_output=True,
            cwd=self.options.cwd,
            env=env,
        )
        return checker_kls(
            runner=self,
            result=expectations.RunResult(
                exit_code=completed.returncode,
                stdout=completed.stdout.decode(),
                stderr=completed.stderr.decode(),
            ),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class SameProcessMypyRunner(Generic[protocols.T_Scenario]):
    options: protocols.RunOptions[protocols.T_Scenario]

    def short_display(self) -> str:
        return "inprocess::mypy"

    def run(self) -> protocols.NoticeChecker[protocols.T_Scenario]:
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
            for k, v in self.options.environment_overrides.items():
                if v is None:
                    monkey_patch.delenv(k, raising=False)
                else:
                    monkey_patch.setenv(k, v)

            if (cwd_str := str(self.options.cwd)) not in sys.path:
                sys.path.insert(0, cwd_str)

            stdout = io.StringIO()
            stderr = io.StringIO()

            with stdout, stderr:
                exit_code = self._run_inprocess(self.options, stdout=stdout, stderr=stderr)

            return MypyChecker(
                runner=self,
                result=expectations.RunResult(
                    exit_code=exit_code,
                    stdout=stdout.getvalue(),
                    stderr=stderr.getvalue(),
                ),
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


@dataclasses.dataclass(frozen=True, kw_only=True)
class DaemonMypyChecker(MypyChecker[protocols.T_Scenario]):
    def check(
        self,
        expected_notices: protocols.ProgramNotices,
    ) -> None:
        lines: list[str] = [
            line
            for line in self.result.stdout.strip().split("\n")
            if not line.startswith(":debug:")
        ]
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

        self._check_lines(lines, expected_notices)
        self.check_daemon_restarted(restarted=daemon_restarted)

    def check_daemon_restarted(self, *, restarted: bool) -> None:
        if self.runner.options.scenario_runner.scenario.expects.daemon_restarted:
            # Followup run should not restart the daemon again
            self.runner.options.scenario_runner.scenario.expects.daemon_restarted = False

            # We expected a restart, assert we did actually restart
            assert restarted
        else:
            assert not restarted


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExternalDaemonMypyRunner(ExternalMypyRunner[protocols.T_Scenario]):
    mypy_name: ClassVar[str] = "mypy.dmypy"

    def __post_init__(self) -> None:
        if self.options.scenario_runner.scenario.same_process:
            raise ValueError(
                "The DAEMON strategy cannot also be in run in the same pytest process"
            )

    def short_display(self) -> str:
        return " ".join(self.command)

    def run(
        self, checker_kls: type[MypyChecker[protocols.T_Scenario]] = DaemonMypyChecker
    ) -> protocols.NoticeChecker[protocols.T_Scenario]:
        """
        Run dmypy as an external process
        """
        self.options.cleaners.add(
            f"program_runner::dmypy::{self.options.cwd}",
            functools.partial(self._cleanup, cwd=self.options.cwd),
        )
        checker = super().run(checker_kls=checker_kls)
        lines = checker.result.stdout.strip().split("\n")

        # dmypy can return exit_code=1 even if it was successful
        exit_code = checker.result.exit_code
        if lines and lines[-1].startswith("Success: no issues found"):
            exit_code = 0

        return checker_kls(
            runner=self,
            result=expectations.RunResult(
                exit_code=exit_code, stdout=checker.result.stdout, stderr=checker.result.stderr
            ),
        )

    def _cleanup(self, *, cwd: pathlib.Path) -> None:
        completed = subprocess.run([*self.command, "status"], capture_output=True, cwd=cwd)
        if completed.returncode == 0:
            completed = subprocess.run([*self.command, "kill"], capture_output=True, cwd=cwd)
            assert (
                completed.returncode == 0
            ), f"Failed to stop dmypy: {completed.returncode}\n{completed.stdout.decode()}\n{completed.stderr.decode()}"


if TYPE_CHECKING:
    _RO: protocols.RunOptions[protocols.P_Scenario] = cast(RunOptions[protocols.P_Scenario], None)

    _EMR: protocols.P_ProgramRunner = cast(ExternalMypyRunner[protocols.P_Scenario], None)
    _SPM: protocols.P_ProgramRunner = cast(SameProcessMypyRunner[protocols.P_Scenario], None)
    _EDMR: protocols.P_ProgramRunner = cast(ExternalDaemonMypyRunner[protocols.P_Scenario], None)
    _MC: protocols.P_NoticeChecker = cast(MypyChecker[protocols.P_Scenario], None)
    _DC: protocols.P_NoticeChecker = cast(DaemonMypyChecker[protocols.P_Scenario], None)
