from __future__ import annotations

import enum
import pathlib
from collections.abc import Iterator, Mapping, MutableMapping, MutableSequence, Sequence
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict, TypeVar, cast, overload

from typing_extensions import NotRequired, Self, Unpack

T_Scenario = TypeVar("T_Scenario", bound="Scenario")
T_CO_Scenario = TypeVar("T_CO_Scenario", bound="Scenario", covariant=True)
T_CO_ScenarioFile = TypeVar("T_CO_ScenarioFile", bound="P_ScenarioFile", covariant=True)


class Strategy(enum.Enum):
    """
    The caching strategy used by the plugin

    MYPY_NO_INCREMENTAL
      - mypy is run only once for each run with --no-incremental

    MYPY_INCREMENTAL
      - mypy is run twice for each run with --incremental.
      - First with an empty cache relative to the temporary directory
      - and again after that cache is made.

    MYPY_DAEMON
      - A new dmypy is started and run twice for each run
    """

    MYPY_NO_INCREMENTAL = "MYPY_NO_INCREMENTAL"
    MYPY_INCREMENTAL = "MYPY_INCREMENTAL"
    MYPY_DAEMON = "MYPY_DAEMON"


class RunCleaner(Protocol):
    """
    Callable used to perform some cleanup action
    """

    def __call__(self) -> None: ...


class RunCleaners(Protocol):
    """
    A collection of :protocol:`RunCleaner` objects
    """

    def add(self, unique_identifier: str, cleaner: RunCleaner, /) -> None:
        """
        Register a cleaner.

        If a cleaner with this identifier has already been registered then it will
        be overridden
        """

    def __iter__(self) -> Iterator[RunCleaner]:
        """
        Yield all the unique cleaners
        """


class RunOptions(Protocol[T_Scenario]):
    """
    Used to represent the options used to run a type checker. This is a mutable object
    so that the scenario runner may modify it before it is used
    """

    scenario: T_Scenario
    typing_strategy: Strategy
    cwd: pathlib.Path
    runner: ProgramRunner[T_Scenario]
    args: MutableSequence[str]
    check_paths: MutableSequence[str]
    do_followup: bool
    environment_overrides: MutableMapping[str, str | None]
    cleaners: RunCleaners


class FileModifier(Protocol):
    """
    Represents a function that can change a file in the scenario

    Implementations should aim to consider the signature as follows:

    :param path: A string representing the path from the root dir to a file
    :param content:
        Passed in as ``None`` if the file is to be deleted, otherwise the content
        to override the file with
    """

    def __call__(self, *, path: str, content: str | None) -> None: ...


class RunResult(Protocol[T_Scenario]):
    """
    Used to represent the options used to run a type checker and the result from doing so
    """

    @property
    def options(self) -> RunOptions[T_Scenario]:
        """
        The scenario that is being tested
        """

    @property
    def exit_code(self) -> int:
        """
        The exit code from running the type checker
        """

    @property
    def stdout(self) -> str:
        """
        The stdout from running the type checker
        """

    @property
    def stderr(self) -> str:
        """
        The stderr from running the type checker
        """


class RunnerConfig(Protocol):
    """
    An object to represent all the options relevant to this pytest plugin

    A default implementation is provided by ``pytest_typing_runner.RunnerConfig``
    """

    @property
    def same_process(self) -> bool:
        """
        Set by the --same-process option.

        Used to know if the type checker should be run in the same process or not.
        """

    @property
    def typing_strategy(self) -> Strategy:
        """
        Set by the --typing-strategy option.

        Used to know what type checker should be used and how.
        """


class ProgramRunner(Protocol[T_Scenario]):
    """
    Used to run the static type checker
    """

    def run(self, options: RunOptions[T_Scenario]) -> RunResult[T_Scenario]:
        """
        Run the static type checker and return a result
        """

    def check_notices(
        self,
        *,
        result: RunResult[T_Scenario],
        expected_notices: ProgramNotices,
    ) -> None:
        """
        Used to check the output against the notices in the expectations
        """

    def short_display(self) -> str:
        """
        Return a string to represent the command that was run
        """


class ScenarioRun(Protocol[T_Scenario]):
    """
    Used to hold information about a single run of a type checker
    """

    @property
    def is_first(self) -> bool:
        """
        Whether this is the first run for this scenario
        """

    @property
    def is_followup(self) -> bool:
        """
        Whether this is a followup run
        """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario that was run
        """

    @property
    def file_modifications(self) -> Sequence[tuple[str, str]]:
        """
        The file modifications that were done before this run
        """

    @property
    def options(self) -> RunOptions[T_Scenario]:
        """
        The options that were used for the run
        """

    @property
    def result(self) -> RunResult[T_Scenario]:
        """
        The result from running the type checker
        """

    @property
    def expectations(self) -> Expectations[T_Scenario]:
        """
        The expectations that were used on this run
        """

    @property
    def expectation_error(self) -> Exception | None:
        """
        Any error from matching the result to the expectations for that run
        """

    def for_report(self) -> Iterator[str]:
        """
        Used to yield strings returned to present in the pytest report
        """


class ScenarioRuns(Protocol[T_Scenario]):
    """
    Represents information to return in a pytest report at the end of the test

    A default implementation is provided by ``pytest_typing_runner.ScenarioRuns``
    """

    @property
    def has_runs(self) -> bool:
        """
        Whether there were any runs to report
        """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario these runs belong to
        """

    def for_report(self) -> Iterator[str]:
        """
        Used to yield strings to place into the pytest report
        """

    def add_file_modification(self, path: str, action: str) -> None:
        """
        Used to record a file modification for the next run
        """

    def add_run(
        self,
        *,
        options: RunOptions[T_Scenario],
        result: RunResult[T_Scenario],
        expectations: Expectations[T_Scenario],
        expectation_error: Exception | None,
    ) -> ScenarioRun[T_Scenario]:
        """
        Used to add a single run to the record
        """


class Severity(Protocol):
    """
    Used to represent the severity of a notice
    """

    @property
    def display(self) -> str:
        """
        Return the severity as a string
        """

    def __eq__(self, other: object) -> bool:
        """
        Determine if this is equal to another object
        """

    def __lt__(self, other: Severity) -> bool:
        """
        To allow ordering a sequence of severity objects
        """


class ProgramNoticesChanger(Protocol):
    def __call__(self, notices: ProgramNotices, /) -> ProgramNotices: ...


class FileNoticesChanger(Protocol):
    def __call__(self, notices: FileNotices, /) -> FileNotices: ...


class LineNoticesChanger(Protocol):
    def __call__(self, notices: LineNotices, /) -> LineNotices | None: ...


class ProgramNoticeChanger(Protocol):
    def __call__(self, notice: ProgramNotice, /) -> ProgramNotice | None: ...


class ProgramNoticeCloneKwargs(TypedDict):
    line_number: NotRequired[int]
    col: NotRequired[int | None]
    severity: NotRequired[Severity]
    msg: NotRequired[str]


class ProgramNotice(Protocol):
    """
    Represents a single notice from the static type checker
    """

    @property
    def location(self) -> pathlib.Path:
        """
        The file this notice is contained in
        """

    @property
    def line_number(self) -> int:
        """
        The line number this notice appears on
        """

    @property
    def col(self) -> int | None:
        """
        The column this notice is found on, if one is provided
        """

    @property
    def severity(self) -> Severity:
        """
        The severity of the notice
        """

    @property
    def msg(self) -> str:
        """
        The message attached to the notice, dedented and including newlines
        """

    @property
    def is_type_reveal(self) -> bool:
        """
        Returns whether this notice represents output from a `reveal_type(...)` instruction
        """

    def clone(self, **kwargs: Unpack[ProgramNoticeCloneKwargs]) -> Self:
        """
        Return a clone with specific changes
        """

    def __lt__(self, other: ProgramNotice) -> bool:
        """
        Make Program notices Orderable
        """

    def matches(self, other: ProgramNotice) -> bool:
        """
        Return whether this matches the provided notice
        """

    def display(self) -> str:
        """
        Return a string form for display
        """


class DiffFileNotices(Protocol):
    """
    Represents the left/right of a diff between notices for a file
    """

    def __iter__(
        self,
    ) -> Iterator[tuple[int, Sequence[ProgramNotice], Sequence[ProgramNotice]]]: ...


class DiffNotices(Protocol):
    """
    Represents the difference between two ProgramNotices per file
    """

    def __iter__(self) -> Iterator[tuple[str, DiffFileNotices]]: ...


class LineNotices(Protocol):
    """
    Represents the information returned by the static type checker for a specific line in a file
    """

    @property
    def line_number(self) -> int:
        """
        The line number these notices are for
        """

    @property
    def location(self) -> pathlib.Path:
        """
        The path to this file as represented by the type checker
        """

    @property
    def has_notices(self) -> bool:
        """
        Whether this has any notices
        """

    def __iter__(self) -> Iterator[ProgramNotice]:
        """
        Yield all the notices
        """

    @overload
    def set_notices(
        self, notices: Sequence[ProgramNotice | None], *, allow_empty: Literal[True]
    ) -> Self: ...

    @overload
    def set_notices(
        self, notices: Sequence[ProgramNotice | None], *, allow_empty: Literal[False] = False
    ) -> Self | None: ...

    def set_notices(
        self, notices: Sequence[ProgramNotice | None], *, allow_empty: bool = False
    ) -> Self | None:
        """
        Return a copy where the chosen notice(s) are replaced

        :param notices: The notices the clone should have. Any None entries are dropped
        :param allow_empty: If False then None is returned instead of a copy with an empty list
        """

    def generate_notice(
        self, *, msg: str, severity: Severity | None = None, col: int | None = None
    ) -> ProgramNotice:
        """
        Generate a notice for this location and line

        This does not add the notice to this LineNotices
        """


class FileNotices(Protocol):
    """
    Represents the information returned by the static type checker for a specific file
    """

    @property
    def location(self) -> pathlib.Path:
        """
        The path to this file as represented by the type checker
        """

    @property
    def has_notices(self) -> bool:
        """
        Whether this file has notices
        """

    def __iter__(self) -> Iterator[ProgramNotice]:
        """
        Yield all the notices
        """

    def get_line_number(self, name_or_line: str | int, /) -> int | None:
        """
        Given a name or line number, return a line number or None if that line number
        doesn't have any notices
        """

    def notices_at_line(self, line_number: int) -> LineNotices | None:
        """
        Return the line notices for a specific line number if there are any
        """

    def generate_notices_for_line(self, line_number: int) -> LineNotices:
        """
        Return a line notices for this location at the specified line

        Implementations should not add this generated object to itself.
        """

    def set_name(self, name: str, line_number: int) -> Self:
        """
        Associate a name with a specific line number
        """

    def set_lines(self, notices: Mapping[int, LineNotices | None]) -> Self:
        """
        Return a modified notices with these notices for the specified line numbers

        Any None values will result in that line number being removed
        """

    def clear(self, *, clear_names: bool) -> Self:
        """
        Return a modified file notices with all notices removed

        :param clear_names: Whether to clear names as well
        """


class FileNoticesParser(Protocol):
    """
    Used to parse notices from comments in a file
    """

    def __call__(self, location: pathlib.Path) -> FileNotices: ...


class ProgramNotices(Protocol):
    """
    Represents the information returned by the static type checker
    """

    @property
    def has_notices(self) -> bool:
        """
        Whether there were any notices
        """

    def __iter__(self) -> Iterator[ProgramNotice]:
        """
        Yield all the notices
        """

    def diff(self, root_dir: pathlib.Path, other: ProgramNotices) -> DiffNotices:
        """
        Return an object representing what is the same and what is different between two program notices
        """

    def notices_at_location(self, location: pathlib.Path) -> FileNotices | None:
        """
        Return the notices for this location if any
        """

    def set_files(self, notices: Mapping[pathlib.Path, FileNotices | None]) -> Self:
        """
        Return a copy with these notices for the specified files
        """

    def generate_notices_for_location(self, location: pathlib.Path) -> FileNotices:
        """
        Return a file notices for this location

        Implementations should not modify this ProgramNotices
        """


class Expectations(Protocol[T_Scenario]):
    """
    This objects knows what to expect from running the static type checker
    """

    def check_results(self, result: RunResult[T_Scenario]) -> None:
        """
        Used to check the result against these expectations
        """


class ExpectationsMaker(Protocol[T_Scenario]):
    """
    Callable that creates an Expectations object
    """

    def __call__(
        self,
        scenario_runner: ScenarioRunner[T_Scenario],
        options: RunOptions[T_Scenario],
    ) -> Expectations[T_Scenario]: ...


class Scenario(Protocol):
    """
    Used to hold relevant information for running and testing a type checker run.

    This object is overridden to provide a mechanism for stringing custom data throughout
    all the other objects.

    A default implementation is provided by ``pytest_typing_runner.Scenario``

    The ``typing_scenario_maker`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.
    """

    same_process: bool
    typing_strategy: Strategy
    root_dir: pathlib.Path
    check_paths: list[str]
    expect_fail: bool
    expect_dmypy_restarted: bool

    def execute_static_checking(
        self: T_Scenario, file_modification: FileModifier, options: RunOptions[T_Scenario]
    ) -> RunResult[T_Scenario]:
        """
        Called to use the run options to run a type checker and get a result
        """

    def parse_notices_from_file(self, location: pathlib.Path) -> FileNotices:
        """
        Used to find comments in a file that represent expected notices
        """

    def check_results(
        self: T_Scenario, result: RunResult[T_Scenario], expectations: Expectations[T_Scenario]
    ) -> None:
        """
        Called to check the result against expectations
        """

    def generate_program_notices(self) -> ProgramNotices:
        """
        Return an object that satisfies an empty :protocol:`ProgramNotices`
        """


class ScenarioRunner(Protocol[T_Scenario]):
    """
    Used to facilitate the running and testing of a type checker run.

    A default implementation is provided by ``pytest_typing_runner.ScenarioRunner``

    The ``typing_`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.
    """

    @property
    def scenario(self) -> T_Scenario:
        """
        The scenario under test
        """

    @property
    def cleaners(self) -> RunCleaners:
        """
        An object to register cleanup functions for the end of the run
        """

    def run_and_check(self, make_expectations: ExpectationsMaker[T_Scenario]) -> None:
        """
        Used to do a run of a type checker and check against the provided expectations
        """

    @property
    def runs(self) -> ScenarioRuns[T_Scenario]:
        """
        The runs of the type checker for this scenario
        """

    def prepare_scenario(self) -> None:
        """
        Called when the scenario has been created. This method may do any mutations it
        wants on self.scenario
        """

    def cleanup_scenario(self) -> None:
        """
        Called after the test is complete. This method may do anything it wants for cleanup
        """

    def add_to_pytest_report(self, name: str, sections: list[tuple[str, str]]) -> None:
        """
        Used to add a section to the pytest report
        """

    def determine_options(self) -> RunOptions[T_Scenario]:
        """
        Called to determine what to run the type checker with
        """

    def file_modification(self, path: str, content: str | None) -> None:
        """
        Used to modify a file for the scenario and record it on the runs
        """


class ScenarioMaker(Protocol[T_CO_Scenario]):
    """
    Represents a callable that creates Scenario objects
    """

    def __call__(self, *, config: RunnerConfig, root_dir: pathlib.Path) -> T_CO_Scenario: ...


class ScenarioRunnerMaker(Protocol[T_Scenario]):
    """
    Represents an object that creates Scenario Runner objects
    """

    def __call__(
        self,
        *,
        config: RunnerConfig,
        root_dir: pathlib.Path,
        scenario_maker: ScenarioMaker[T_Scenario],
    ) -> ScenarioRunner[T_Scenario]: ...


class ScenarioFile(Protocol):
    """
    Used to hold information about a file in a scenario
    """

    @property
    def root_dir(self) -> pathlib.Path:
        """
        The root dir of the scenario
        """

    @property
    def path(self) -> str:
        """
        The path to this file relative to the rootdir
        """

    def notices(self) -> FileNotices | None:
        """
        Return the notices associated with this file
        """


class ScenarioFileMaker(Protocol[T_CO_ScenarioFile]):
    """
    Callable that returns a ScenarioFile
    """

    def __call__(self, *, root_dir: pathlib.Path, path: str) -> T_CO_ScenarioFile: ...


if TYPE_CHECKING:
    P_Scenario = Scenario

    P_ScenarioFile = ScenarioFile
    P_ScenarioRun = ScenarioRun[P_Scenario]
    P_ScenarioRuns = ScenarioRuns[P_Scenario]
    P_Expectations = Expectations[P_Scenario]
    P_ScenarioMaker = ScenarioMaker[P_Scenario]
    P_ScenarioRunner = ScenarioRunner[P_Scenario]
    P_ScenarioFileMaker = ScenarioFileMaker[P_ScenarioFile]
    P_ExpectationsMaker = ExpectationsMaker[P_Scenario]
    P_ScenarioRunnerMaker = ScenarioRunnerMaker[P_Scenario]

    P_Severity = Severity
    P_FileNotices = FileNotices
    P_LineNotices = LineNotices
    P_ProgramNotice = ProgramNotice
    P_ProgramNotices = ProgramNotices
    P_FileNoticesParser = FileNoticesParser
    P_ProgramNoticesChanger = ProgramNoticesChanger
    P_FileNoticesChanger = FileNoticesChanger
    P_LineNoticesChanger = FileNoticesChanger
    P_ProgramNoticeChanger = ProgramNoticeChanger
    P_DiffNotices = DiffNotices
    P_DiffFileNotices = DiffFileNotices

    P_FileModifier = FileModifier
    P_RunOptions = RunOptions[P_Scenario]
    P_RunResult = RunResult[P_Scenario]
    P_RunnerConfig = RunnerConfig
    P_ProgramRunner = ProgramRunner[P_Scenario]
    P_RunCleaner = RunCleaner
    P_RunCleaners = RunCleaners

    _FM: P_FileModifier = cast(P_ScenarioRunner, None).file_modification
