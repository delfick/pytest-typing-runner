from __future__ import annotations

import dataclasses
import pathlib
import shutil
import textwrap
from collections.abc import Iterator, MutableMapping, MutableSequence, Sequence, Set
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import notices, protocols


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunnerConfig:
    """
    Holds the defaults received from pytest command line options

    Implements :protocol:`pytest_typing_runner.protocols.RunnerConfig`

    :param same_process:
        The default used for `same_process`` on the Scenario.
    :typing_strategy:
        Used when creating the :protocol:`pytest_typing_runner.protocols.Scenario`
    """

    same_process: bool
    typing_strategy: protocols.Strategy


@dataclasses.dataclass
class Expects:
    """
    Holds boolean expectations from running the type checker in the scenario

    Implements :protocol:`pytest_typing_runner.protocols.Expects`

    :param failure: Whether we expect the test to raise a difference in notices
    :param daemon_restarted:
        Used when a type checker is used that depends on a daemon and
        indicates whether the scenario believes the daemon will be restarted
        in the next run of the type checker.
    """

    failure: bool = False
    daemon_restarted: bool = False


@dataclasses.dataclass(frozen=True, kw_only=True)
class Scenario:
    """
    The heart of each pytest typing runner test. Everything is in terms of a specific implementation
    of scenario. The idea is that when customising what the plugin does, this object is the only
    one where apis can be added.

    The other objects are generic to the specific implementation of Scenario.

    Implements :protocol:`pytest_typing_runner.protocols.Scenario`

    :param root_dir: The directory to place all the files in for the scenario.
    :param expects: A container of boolean expectations
    """

    root_dir: pathlib.Path
    expects: Expects = dataclasses.field(init=False, default_factory=Expects)

    @classmethod
    def create(cls, config: protocols.RunnerConfig, root_dir: pathlib.Path) -> Self:
        """
        A handy helper that implements :protocol:`pytest_typing_runner.protocols.ScenarioMaker`
        """
        return cls(root_dir=root_dir)


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunCleaners:
    """
    Object that holds cleanup functions to be run at the end of the test.

    Implements :protocol:`pytest_typing_runner.protocols.RunCleaners`

    .. automethod:: __iter__
    """

    _cleaners: MutableMapping[str, protocols.RunCleaner] = dataclasses.field(
        init=False, default_factory=dict
    )

    def add(self, unique_identifier: str, cleaner: protocols.RunCleaner) -> None:
        """
        Registers a cleaner to some unique identifier.

        Note if the identifier has already been registered then the cleaner at
        that identifier will be silently replaced

        :param unique_identifier: The name of the cleaner
        :param cleaner: The callable that performs some cleanup
        """
        self._cleaners[unique_identifier] = cleaner

    def __iter__(self) -> Iterator[protocols.RunCleaner]:
        """
        Yield the registered cleaners in the order they were added.
        """
        yield from self._cleaners.values()


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRun(Generic[protocols.T_Scenario]):
    """
    Holds the information for a single run of the type checker in the test.

    Implements :protocol:`pytest_typing_runner.protocols.ScenarioRun`

    :param is_first: Whether this is the first run
    :param is_followup:
        Whether this is a followup run (so nothing has changed since last run)
    :param checker:
        The object that represents the result, runner and check logic from the run
    :param expectations:
        Represents the notices that were expected from the run
    :param expectation_error:
        Any error from matching the result to the expectations for that run
    :param file_modifications:
        A list of ``(path, action)`` for the file changes that setup the scenario.
    """

    is_first: bool
    is_followup: bool
    checker: protocols.NoticeChecker[protocols.T_Scenario]
    expectation_error: Exception | None
    file_modifications: Sequence[tuple[str, str]]

    def for_report(self) -> Iterator[str]:
        """
        Yields lines that can be displayed in a pytest report

        * displays path/action from ``file_modifications``
        * displays ``[followup run]`` if ``is_followup`` else displays the combination
          of ``short_display()`` from ``checker.runner`` and the ``args`` and
          ``check_paths`` on ``checker.run_options``
        * displays the ``exit_code`` from ``checker.result``
        * displays each line in ``stdout`` and ``stderr`` from ``checker.result``
        * displays the ``expectation_error`` if there was one.
        """
        for path, action in self.file_modifications:
            yield f"* {action:10s}: {path}"

        if self.is_followup:
            yield "> [followup run]"
        else:
            command = " ".join(
                [
                    self.checker.runner.short_display(),
                    *self.checker.run_options.args,
                    *self.checker.run_options.check_paths,
                ]
            )
            yield f"> {command}"

        yield f"| exit_code={self.checker.result.exit_code}"
        for line in self.checker.result.stdout.split("\n"):
            l = line.rstrip()
            if l:
                l = f" {l}"
            yield f"| stdout:{l}"
        for line in self.checker.result.stderr.split("\n"):
            l = line.rstrip()
            if l:
                l = f" {l}"
            yield f"| stderr:{l}"
        if self.expectation_error:
            yield f"!!! <{self.expectation_error.__class__.__name__}> {self.expectation_error}"


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRuns(Generic[protocols.T_Scenario]):
    """
    A collection of scenario runs for a test.

    Implements :protocol:`pytest_typing_runner.protocols.ScenarioRuns`

    :param scenario: The scenario runs are being collected for
    """

    scenario: protocols.T_Scenario
    _runs: MutableSequence[protocols.ScenarioRun[protocols.T_Scenario]] = dataclasses.field(
        init=False, default_factory=list
    )
    _file_modifications: list[tuple[str, str]] = dataclasses.field(
        init=False, default_factory=list
    )
    _known_files: MutableSequence[str] = dataclasses.field(init=False, default_factory=list)

    @classmethod
    def create(cls, *, scenario: protocols.T_Scenario) -> Self:
        """
        Helpful classmethod implementing :protocol:`pytest_typing_runner.protocols.ScenarioRunsMaker`
        """
        return cls(scenario=scenario)

    @property
    def known_files(self) -> Set[str]:
        """
        Return all the files that were modified across all runs
        """
        return set(self._known_files)

    def for_report(self) -> Iterator[str]:
        """
        Yields lines for a pytest report indented and with a heading for each run.
        """
        for i, run in enumerate(self._runs):
            yield f":: Run {i + 1}"
            for line in run.for_report():
                yield f"   | {line}"

    @property
    def has_runs(self) -> bool:
        """
        Return whether this holds any runs
        """
        return bool(self._runs)

    def add_file_modification(self, path: str, action: str) -> None:
        """
        Record a file modification for the current run
        """
        self._known_files.append(path)
        self._file_modifications.append((path, action))

    def add_run(
        self,
        *,
        checker: protocols.NoticeChecker[protocols.T_Scenario],
        expectation_error: Exception | None,
    ) -> protocols.ScenarioRun[protocols.T_Scenario]:
        """
        Used to add a single run to the record

        Will take the ``file_modifications`` recorded on the collection and create
        the ``ScenarioRun`` with those modifications before clearing it on the
        collection.

        :param checker: The result of running the type checker
        :param expectation_error:
            The error from checking expectations if there was one
        """
        file_modifications = tuple(self._file_modifications)
        self._file_modifications.clear()

        run = ScenarioRun(
            is_first=not self.has_runs,
            is_followup=checker.run_options.do_followup and len(self._runs) == 1,
            checker=checker,
            expectation_error=expectation_error,
            file_modifications=file_modifications,
        )
        self._runs.append(run)
        return run


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioRunner(Generic[protocols.T_Scenario]):
    """
    Holds logic for creating and using objects that hold onto the scenario.

    Implements :protocol:`pytest_typing_runner.protocols.ScenarioRuns`

    :param scenario: The scenario being controlled
    :param default_program_runner_maker: Default maker for the program runner
    :param runs: Used to hold a record of each run of the type checker
    :param cleaners:
        A collection of cleanup functions that are used in the pytest fixture
        that provides an instance of the ``ScenarioRunner`` to perform any
        cleanup at the end of the run
    :param default_msg_maker: Default used by ScenarioRunner when generating program notices
    """

    scenario: protocols.T_Scenario
    runs: protocols.ScenarioRuns[protocols.T_Scenario]
    cleaners: protocols.RunCleaners
    default_program_runner_maker: protocols.ProgramRunnerMaker[protocols.T_Scenario]
    default_msg_maker: protocols.NoticeMsgMaker

    @classmethod
    def create(
        cls,
        *,
        config: protocols.RunnerConfig,
        root_dir: pathlib.Path,
        scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
        scenario_runs_maker: protocols.ScenarioRunsMaker[protocols.T_Scenario],
        default_msg_maker: protocols.NoticeMsgMaker = notices.PlainMsg.create,
    ) -> Self:
        """
        Helpful classmethod that implements :protocol:`pytest_typing_runner.protocols.ScenarioRunnerMaker`

        :param config: The pytest typing runner options from pytest command line
        :param root_dir: The directory files for the scenario should be placed
        :param scenario_maker: Used to create the scenario itself
        :param scenario_runs_maker: Used to create the ``runs`` container
        """
        scenario = scenario_maker(config=config, root_dir=root_dir)
        return cls(
            scenario=scenario,
            default_program_runner_maker=config.typing_strategy.program_runner_chooser(
                config=config, scenario=scenario
            ),
            runs=scenario_runs_maker(scenario=scenario),
            cleaners=RunCleaners(),
            default_msg_maker=default_msg_maker,
        )

    def prepare_scenario(self) -> None:
        """
        Default implementation does not need to do any extra preparation
        """

    def cleanup_scenario(self) -> None:
        """
        Default implementation does not need to do any extra cleanup
        """

    def add_to_pytest_report(self, name: str, sections: list[tuple[str, str]]) -> None:
        """
        Default implementation adds a section with the provided name if there were runs to report

        :param name: The name of the report
        :param sections: The pytest report sections to add to
        """
        if self.runs.has_runs:
            sections.append((name, "\n".join(self.runs.for_report())))

    def file_modification(self, path: str, content: str | None) -> None:
        """
        Change a file in ``root_dir`` and record the action.

        All changes to the files in the scenario should be done through this
        function so that the pytest report is complete.

        There are :ref:`helpers for changing files <file_changer>` that can be
        used to perform high level changes with this hook.

        :param path: The string path relative to ``root_dir`` to change
        :param content:
            Either a string to replace the whole file, or ``None`` if the file
            should be deleted.
        """
        location = self.scenario.root_dir / path
        if not location.is_relative_to(self.scenario.root_dir):
            raise ValueError("Tried to modify a file outside of the test root")

        if location.exists():
            if content is None:
                action = "delete"
                if location.is_dir():
                    shutil.rmtree(location)
                else:
                    location.unlink()
            else:
                action = "change"
                new_content = textwrap.dedent(content)
                if location.read_text() == new_content:
                    return
                location.write_text(new_content)
        else:
            if content is None:
                action = "already_deleted"
            else:
                action = "create"
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_text(textwrap.dedent(content))

        self.runs.add_file_modification(path, action)

    def execute_static_checking(
        self, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.NoticeChecker[protocols.T_Scenario]:
        """
        Used to run the type checker.

        By default it uses ``program_runner_maker`` on the options to create
        a program runner and the ``run`` method is called, passing on the result

        :param options: The run options
        :returns:
            A :protocol:`pytest_typing_runner.protocols.NoticeChecker` object
            representing what was run, the result, and how to check it.
        """
        return options.program_runner_maker(options=options).run()

    def run_and_check(
        self,
        *,
        options: protocols.RunOptions[protocols.T_Scenario],
        setup_expectations: protocols.ExpectationsSetup[protocols.T_Scenario],
    ) -> None:
        """
        Used to run the type checker followed by checking and recording the result.

        The ``setup_expectations`` passed in should perform any extra setup before
        creating and running the type checker.

        The result of ``setup_expectations`` is used after the type checker has
        run to determine what was expected from that run.

        This is used to check the run before recording the result on ``self.runs``.

        .. note:: Running the type checker is done by calling the implementation
            of ``execute_static_checking`` on this scenario runner instance.

        If ``options.do_followup`` is ``True`` and it's the first run for this
        scenario, and there was no error when checking the result, then
        ``execute_static_checking`` is called again with the same
        run options and checked against the same expectations. The idea is that
        running the type checker again without any changes should produce the
        same result.

        :param setup_expectations:
            Used to do setup before running the type checker and how to determine
            what result is expected from the type checker
        """
        make_expectations = setup_expectations(options=options)
        checker = self.execute_static_checking(options=options)
        expectations = make_expectations()

        try:
            expectations.check(notice_checker=checker)
        except Exception as err:
            run = self.runs.add_run(checker=checker, expectation_error=err)
            if not self.scenario.expects.failure:
                raise
        else:
            run = self.runs.add_run(checker=checker, expectation_error=None)
            assert not self.scenario.expects.failure, "expected assertions to fail"

        if options.do_followup and run.is_first:
            repeat_expectations: protocols.ExpectationsSetup[protocols.T_Scenario] = (
                lambda options: lambda: expectations
            )
            self.run_and_check(setup_expectations=repeat_expectations, options=options)

        # Make it necessary to reset this explicitly every time
        self.scenario.expects.failure = False

    def normalise_program_runner_notice(
        self,
        options: protocols.RunOptions[protocols.T_Scenario],
        notice: protocols.ProgramNotice,
        /,
    ) -> protocols.ProgramNotice:
        """
        This is a hook that is available to be used by parsers of runner
        output to do any required normalisation of type checker output.
        """
        return notice

    def generate_program_notices(
        self, *, msg_maker: protocols.NoticeMsgMaker | None = None
    ) -> protocols.ProgramNotices:
        """
        Returns a default implementation of :protocol:`pytest_typing_runner.ProgramNotices`
        """
        if msg_maker is None:
            msg_maker = self.default_msg_maker
        return notices.ProgramNotices(msg_maker=msg_maker)


if TYPE_CHECKING:
    C_Scenario = Scenario
    C_RunnerConfig = RunnerConfig
    C_ScenarioRun = ScenarioRun[C_Scenario]
    C_ScenarioRuns = ScenarioRuns[C_Scenario]
    C_ScenarioRunner = ScenarioRunner[C_Scenario]

    _RC: protocols.P_RunnerConfig = cast(C_RunnerConfig, None)

    _CS: protocols.P_Scenario = cast(C_Scenario, None)
    _CSR: protocols.ScenarioRuns[C_Scenario] = cast(C_ScenarioRuns, None)
    _CSM: protocols.ScenarioMaker[C_Scenario] = C_Scenario.create
    _CSRM: protocols.ScenarioRunsMaker[C_Scenario] = C_ScenarioRuns
    _CSRU: protocols.ScenarioRunner[C_Scenario] = cast(C_ScenarioRunner, None)
    _CSRUM: protocols.ScenarioRunnerMaker[C_Scenario] = C_ScenarioRunner.create

    _E: protocols.Expects = cast(Expects, None)
    _RCS: protocols.RunCleaners = cast(RunCleaners, None)
