import argparse
import pathlib
import sys
from collections.abc import Iterator

import pytest
from pytest_typing_runner_test_driver import executable, stubs

from pytest_typing_runner import protocols, runners, scenarios


@pytest.fixture
def runner(tmp_path: pathlib.Path) -> protocols.ScenarioRunner[protocols.Scenario]:
    return scenarios.ScenarioRunner[protocols.Scenario].create(
        config=stubs.StubRunnerConfig(),
        root_dir=tmp_path,
        scenario_maker=scenarios.Scenario.create,
        scenario_runs_maker=scenarios.ScenarioRuns.create,
    )


class TestExternalMypyRunner:
    @pytest.fixture
    def fake_mypy(self) -> Iterator[tuple[pathlib.Path, str]]:
        def make_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser()
            parser.add_argument("--for-stderr", type=pathlib.Path, required=False)
            parser.add_argument("--for-stdout", type=pathlib.Path, required=False)
            parser.add_argument("--fail", action="store_true")
            return parser

        def mainline(argv: list[str], parser: argparse.ArgumentParser, out: pathlib.Path) -> None:
            args, _ = parser.parse_known_args(argv)
            out.write_text(str(pathlib.Path.cwd()) + "\n" + " ".join(argv))

            if args.for_stderr:
                sys.stderr.write(args.for_stderr.read_text())
            if args.for_stdout:
                sys.stdout.write(args.for_stdout.read_text())

            if args.fail:
                sys.exit(1)

        with executable.make_python_module("mypy", make_parser=make_parser, mainline=mainline) as (
            out,
            pythonpath,
        ):
            yield (out, pythonpath)

    def test_it_has_command_and_short_display(
        self,
        runner: protocols.ScenarioRunner[protocols.Scenario],
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.ExternalMypyRunner(options=options)
        assert mypy_runner.command == (sys.executable, "-m", "mypy")
        assert mypy_runner.short_display() == " ".join(mypy_runner.command)

    def test_it_runs_mypy_and_returns_stdout_stderr_and_exit_code(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_mypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\ns6")

        options = runners.RunOptions.create(
            runner,
            args=[
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_mypy[1]},
        )

        mypy_runner = runners.ExternalMypyRunner(options=options)
        checker = mypy_runner.run()

        assert isinstance(checker, runners.MypyChecker)
        assert checker.runner is mypy_runner
        assert checker.result.exit_code == 0
        assert checker.result.stderr == "s1\ns2\ns3"
        assert checker.result.stdout == "s4\ns5\ns6"

        assert (
            fake_mypy[0].read_text()
            == f"{options.cwd}\n--one --for-stderr {stderr_location} --for-stdout {stdout_location} two three"
        )


class TestSameProcessMypyRunner:
    def test_it_has_short_display(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.SameProcessMypyRunner(options=options)
        assert mypy_runner.short_display() == "inprocess::mypy"


class TestExternalDaemonMypyRunner:
    @pytest.fixture
    def fake_dmypy(self) -> Iterator[tuple[pathlib.Path, str]]:
        def make_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser()
            parser.add_argument("action", choices=("run", "status", "kill"))
            parser.add_argument("--for-stderr", type=pathlib.Path, required=False)
            parser.add_argument("--for-stdout", type=pathlib.Path, required=False)
            parser.add_argument("--fail", action="store_true")
            parser.add_argument("--restarts-daemon", action="store_true")
            return parser

        def mainline(argv: list[str], parser: argparse.ArgumentParser, out: pathlib.Path) -> None:
            args, _ = parser.parse_known_args(argv)
            with open(out, "a") as fle:
                fle.write(str(pathlib.Path.cwd()) + "\n" + " ".join(argv) + "\n")

            dmypy_json = pathlib.Path.cwd() / ".dmypy.json"

            if args.action == "run":
                if not dmypy_json.exists():
                    sys.stdout.write("Daemon started\n")
                else:
                    if args.restarts_daemon:
                        sys.stdout.write("Restarting: change\n")
                        sys.stdout.write("Daemon stopped\n")
                        sys.stdout.write("Daemon started\n")

            if args.for_stderr:
                sys.stderr.write(args.for_stderr.read_text())
            if args.for_stdout:
                sys.stdout.write(args.for_stdout.read_text())

            if args.action == "run":
                dmypy_json.write_text("")
                if args.fail:
                    sys.exit(1)
            elif args.action == "status":
                if not dmypy_json.exists():
                    sys.exit(1)
            elif args.action == "kill":
                dmypy_json.unlink(missing_ok=True)

        with executable.make_python_module(
            "mypy/dmypy", make_parser=make_parser, mainline=mainline
        ) as (
            out,
            pythonpath,
        ):
            yield (out, pythonpath)

    def test_it_has_command_and_short_display(
        self, runner: protocols.ScenarioRunner[protocols.Scenario]
    ) -> None:
        options = runners.RunOptions.create(runner, args=["one"])

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)
        assert mypy_runner.command == (sys.executable, "-m", "mypy.dmypy")
        assert mypy_runner.short_display() == " ".join(mypy_runner.command)

    def test_it_runs_dmypy_and_returns_stdout_stderr_and_exit_code(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_dmypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\ns6")

        options = runners.RunOptions.create(
            runner,
            args=[
                "run",
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_dmypy[1]},
        )

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)

        assert len(list(runner.cleaners)) == 0
        checker = mypy_runner.run()

        assert isinstance(checker, runners.MypyChecker)
        assert checker.runner is mypy_runner
        assert checker.result.exit_code == 0
        assert checker.result.stderr == "s1\ns2\ns3"
        assert checker.result.stdout == "Daemon started\ns4\ns5\ns6"

        assert (
            fake_dmypy[0].read_text()
            == f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three\n"
        )

        dmypy_json_location = options.cwd / ".dmypy.json"
        assert dmypy_json_location.exists()
        assert len(list(runner.cleaners)) == 1
        for cleaner in runner.cleaners:
            cleaner()

        assert fake_dmypy[0].read_text() == "\n".join(
            [
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three",
                f"{options.cwd}\nstatus",
                f"{options.cwd}\nkill\n",
            ]
        )

        assert not dmypy_json_location.exists()

    def test_it_forces_exit_code_to_0_if_failed_but_no_errors(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_dmypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\nSuccess: no issues found")

        options = runners.RunOptions.create(
            runner,
            args=[
                "run",
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
                "--fail",
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_dmypy[1]},
        )

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)
        checker = mypy_runner.run()
        assert checker.result.exit_code == 0

    def test_it_does_not_force_exit_code_to_0_if_failed_and_has_errors(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_dmypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\nnot_a_line_that_says_success")

        options = runners.RunOptions.create(
            runner,
            args=[
                "run",
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
                "--fail",
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_dmypy[1]},
        )

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)
        checker = mypy_runner.run()
        assert checker.result.exit_code == 1

    def test_cleanup_doesnt_kill_if_status_says_no(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_dmypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\ns6")

        options = runners.RunOptions.create(
            runner,
            args=[
                "run",
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_dmypy[1]},
        )

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)

        assert len(list(runner.cleaners)) == 0
        checker = mypy_runner.run()

        assert isinstance(checker, runners.MypyChecker)
        assert checker.runner is mypy_runner
        assert checker.result.exit_code == 0
        assert checker.result.stderr == "s1\ns2\ns3"
        assert checker.result.stdout == "Daemon started\ns4\ns5\ns6"

        assert (
            fake_dmypy[0].read_text()
            == f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three\n"
        )

        dmypy_json_location = options.cwd / ".dmypy.json"

        assert dmypy_json_location.exists()
        dmypy_json_location.unlink()
        assert len(list(runner.cleaners)) == 1
        for cleaner in runner.cleaners:
            cleaner()

        assert fake_dmypy[0].read_text() == "\n".join(
            [
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three",
                f"{options.cwd}\nstatus\n",
            ]
        )

        assert not dmypy_json_location.exists()

    def test_cleanup_only_gets_made_once_over_many_runs(
        self,
        tmp_path: pathlib.Path,
        runner: protocols.ScenarioRunner[protocols.Scenario],
        fake_dmypy: tuple[pathlib.Path, str],
    ) -> None:
        stderr_location = tmp_path / "stderr"
        stderr_location.write_text("s1\ns2\ns3")
        stdout_location = tmp_path / "stdout"
        stdout_location.write_text("s4\ns5\ns6")

        options = runners.RunOptions.create(
            runner,
            args=[
                "run",
                "--one",
                "--for-stderr",
                str(stderr_location),
                "--for-stdout",
                str(stdout_location),
            ],
            check_paths=["two", "three"],
            environment_overrides={"PYTHONPATH": fake_dmypy[1]},
        )

        mypy_runner = runners.ExternalDaemonMypyRunner(options=options)

        assert len(list(runner.cleaners)) == 0
        checker = mypy_runner.run()

        assert isinstance(checker, runners.MypyChecker)
        assert checker.runner is mypy_runner
        assert checker.result.exit_code == 0
        assert checker.result.stderr == "s1\ns2\ns3"
        assert checker.result.stdout == "Daemon started\ns4\ns5\ns6"

        assert fake_dmypy[0].read_text() == "\n".join(
            [
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three\n",
            ]
        )

        assert len(list(runner.cleaners)) == 1
        checker = mypy_runner.run()
        assert isinstance(checker, runners.MypyChecker)
        assert checker.runner is mypy_runner
        assert checker.result.exit_code == 0
        assert checker.result.stderr == "s1\ns2\ns3"
        assert checker.result.stdout == "s4\ns5\ns6"

        assert fake_dmypy[0].read_text() == "\n".join(
            [
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three",
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three\n",
            ]
        )

        dmypy_json_location = options.cwd / ".dmypy.json"

        assert dmypy_json_location.exists()
        assert len(list(runner.cleaners)) == 1
        for cleaner in runner.cleaners:
            cleaner()

        assert fake_dmypy[0].read_text() == "\n".join(
            [
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three",
                f"{options.cwd}\nrun --one --for-stderr {stderr_location} --for-stdout {stdout_location} two three",
                f"{options.cwd}\nstatus",
                f"{options.cwd}\nkill\n",
            ]
        )

        assert not dmypy_json_location.exists()
