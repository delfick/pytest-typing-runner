from __future__ import annotations

import pathlib
from collections.abc import Iterator, Mapping, Sequence, Set
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict, TypeVar, cast, overload

from typing_extensions import NotRequired, Self, Unpack

T_Scenario = TypeVar("T_Scenario", bound="Scenario")
T_CO_Scenario = TypeVar("T_CO_Scenario", bound="Scenario", covariant=True)
T_CO_ScenarioFile = TypeVar("T_CO_ScenarioFile", bound="P_ScenarioFile", covariant=True)


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


class RunOptionsCloneArgs(TypedDict):
    """
    Used to represent the options that can be changed when cloning run options
    """

    cwd: NotRequired[pathlib.Path]
    args: NotRequired[Sequence[str]]
    check_paths: NotRequired[Sequence[str]]
    do_followup: NotRequired[bool]
    environment_overrides: NotRequired[Mapping[str, str | None]]


class RunOptions(Protocol[T_Scenario]):
    """
    Used to represent the options used to run a type checker
    """

    @property
    def scenario_runner(self) -> ScenarioRunner[T_Scenario]:
        """
        The scenario runner
        """

    @property
    def cwd(self) -> pathlib.Path:
        """
        The working directory to run the type checker from
        """

    @property
    def program_runner_maker(self) -> ProgramRunnerMaker[T_Scenario]:
        """
        Make the specific type checker to run
        """

    @property
    def args(self) -> Sequence[str]:
        """
        The arguments to pass into the type checker
        """

    @property
    def check_paths(self) -> Sequence[str]:
        """
        The paths to check with the type checker
        """

    @property
    def do_followup(self) -> bool:
        """
        Return whether followup runs should be done
        """

    @property
    def environment_overrides(self) -> Mapping[str, str | None]:
        """
        Overrides of environment variables for when running the type checker
        """

    def clone(
        self,
        *,
        program_runner_maker: ProgramRunnerMaker[T_Scenario] | None = None,
        **kwargs: Unpack[RunOptionsCloneArgs],
    ) -> Self:
        """
        Used to provide a copy with certain options changed
        """


class RunOptionsModify(Protocol[T_Scenario]):
    """
    Represents a function that can return a modified run options
    """

    def __call__(self, options: RunOptions[T_Scenario], /) -> RunOptions[T_Scenario]: ...


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


class NoticeChecker(Protocol[T_Scenario]):
    """
    Used to represent a function that can be wrapped to
    provide a function for checking notices
    """

    @property
    def result(self) -> RunResult:
        """
        The result to check against
        """

    @property
    def run_options(self) -> RunOptions[T_Scenario]:
        """
        The final options used for the run
        """

    @property
    def runner(self) -> ProgramRunner[T_Scenario]:
        """
        The runner that was used to make the result
        """

    def check(self, expected_notices: ProgramNotices, /) -> None: ...


class RunResult(Protocol):
    """
    Used to represent the result of running a type checker
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

    @property
    def options(self) -> RunOptions[T_Scenario]:
        """
        The options for this run
        """

    def run(self) -> NoticeChecker[T_Scenario]:
        """
        Run the static type checker and return a result
        """

    def short_display(self) -> str:
        """
        Return a string to represent the command that was run
        """


class ProgramRunnerMaker(Protocol[T_Scenario]):
    """
    Used to contruct a program runner
    """

    @property
    def default_args(self) -> Sequence[str]:
        """
        The default args to start the program runner with
        """

    @property
    def do_followups(self) -> bool:
        """
        The default for whether the program runner should be used in a followup run
        """

    @property
    def same_process(self) -> bool:
        """
        Whether this program runner executes within this process instead of in a subprocess
        """

    @property
    def is_daemon(self) -> bool:
        """
        Whether this program runner uses a daemon
        """

    @property
    def program_short(self) -> str:
        """
        String representing the family of type checker (i.e. "mypy", "pyright", etc)
        """

    def __call__(self, *, options: RunOptions[T_Scenario]) -> ProgramRunner[T_Scenario]: ...


class ProgramRunnerChooser(Protocol):
    """
    Used to choose which program runner to use
    """

    def __call__(
        self, *, config: RunnerConfig, scenario: T_Scenario
    ) -> ProgramRunnerMaker[T_Scenario]: ...


class Strategy(Protocol):
    @property
    def program_short(self) -> str:
        """
        String representing the family of type checker (i.e. "mypy", "pyright", etc)
        """

    @property
    def program_runner_chooser(self) -> ProgramRunnerChooser:
        """
        Used to make a program runner
        """


class StrategyMaker(Protocol):
    """
    Used to construct an object implementing :protocol:`Strategy`
    """

    def __call__(self) -> Strategy: ...


class StrategyRegistry(Protocol):
    """
    Used to register different typing strategies
    """

    def register(
        self, *, name: str, description: str, maker: StrategyMaker, make_default: bool = False
    ) -> None:
        """
        Register a maker to a specific name
        """

    def remove_strategy(self, *, name: str) -> None:
        """
        Remove a strategy
        """

    def set_default(self, *, name: str) -> None:
        """
        Set the default strategy
        """

    def get_strategy(self, *, name: str) -> tuple[str, StrategyMaker] | None:
        """
        Return the strategy for the provided name if one exists
        """

    @property
    def default(self) -> str:
        """
        Return the default strategy
        """

    @property
    def choices(self) -> list[str]:
        """
        Return the known strategies
        """


class StrategyRegisterer(Protocol):
    """
    Used to register strategies
    """

    def __call__(self, registry: StrategyRegistry, /) -> None: ...


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
    def file_modifications(self) -> Sequence[tuple[str, str]]:
        """
        The file modifications that were done before this run
        """

    @property
    def checker(self) -> NoticeChecker[T_Scenario]:
        """
        The result from running the type checker
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
    def known_files(self) -> Set[str]:
        """
        The paths to all the files created as part of the scenario
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
        self, *, checker: NoticeChecker[T_Scenario], expectation_error: Exception | None
    ) -> ScenarioRun[T_Scenario]:
        """
        Used to add a single run to the record
        """


class ScenarioRunsMaker(Protocol[T_Scenario]):
    """
    Used to construct a scenario runs
    """

    def __call__(self, *, scenario: T_Scenario) -> ScenarioRuns[T_Scenario]: ...


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


class NoticeMsg(Protocol):
    """
    Used to represent the message on a notice and the ability to compare with other messages
    """

    raw: str

    def __str__(self) -> str: ...
    def __eq__(self, o: object, /) -> bool: ...
    def __hash__(self) -> int: ...
    def __lt__(self, o: NoticeMsg, /) -> bool: ...

    @property
    def is_plain(self) -> bool:
        """
        Whether this msg does no pattern matching
        """

    def replace(self, old: str, new: str, count: int = -1) -> Self:
        """
        A shortcut for ``msg.clone(raw=msg.raw.replace(old, new, count))``
        """

    def match(self, *, want: str) -> bool:
        """
        :param want: The string to match against
        :returns: True if ``want`` matches some expectation
        """

    def clone(self, *, pattern: str) -> Self:
        """
        Used to create a version of this msg class but for a different msg
        """

    def split_lines(self) -> Iterator[Self]:
        """
        Yield copies of this notice with a clone per line
        """


class NoticeMsgMaker(Protocol):
    """
    Used to create a NoticeMsg
    """

    def __call__(self, *, pattern: str) -> NoticeMsg: ...


class NoticeMsgMakerMap(Protocol):
    """
    Holds notice msg makers
    """

    @overload
    def get(self, name: str, /, default: NoticeMsgMaker) -> NoticeMsgMaker: ...

    @overload
    def get(self, name: str, /, default: None = None) -> NoticeMsgMaker | None: ...

    def get(
        self, name: str, /, default: NoticeMsgMaker | None = None
    ) -> NoticeMsgMaker | None: ...

    @property
    def available(self) -> Sequence[str]: ...


class ProgramNoticeCloneKwargs(TypedDict):
    line_number: NotRequired[int]
    col: NotRequired[int | None]
    severity: NotRequired[Severity]


class ProgramNoticeCloneAndMsgKwargs(ProgramNoticeCloneKwargs):
    msg: NotRequired[str | NoticeMsg]


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
    def msg(self) -> NoticeMsg:
        """
        The message attached to the notice, dedented and including newlines
        """

    @property
    def is_type_reveal(self) -> bool:
        """
        Returns whether this notice represents output from a `reveal_type(...)` instruction
        """

    def clone(
        self, *, msg: str | NoticeMsg | None = None, **kwargs: Unpack[ProgramNoticeCloneKwargs]
    ) -> Self:
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

    @property
    def msg_maker(self) -> NoticeMsgMaker:
        """
        Implementations should use this when generating a program notice
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
        self,
        *,
        msg: str | NoticeMsg,
        msg_maker: NoticeMsgMaker | None = None,
        severity: Severity | None = None,
        col: int | None = None,
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

    @property
    def known_names(self) -> Mapping[str, int]:
        """
        Return the registered names
        """

    def known_line_numbers(self) -> Iterator[int]:
        """
        Yield the line numbers that have line notices
        """

    @property
    def msg_maker(self) -> NoticeMsgMaker:
        """
        Implementations should pass this on when generating a line notices
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

    def generate_notices_for_line(
        self, line_number: int, *, msg_maker: NoticeMsgMaker | None = None
    ) -> LineNotices:
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

    def __call__(self, content: str, /, *, into: FileNotices) -> tuple[str, FileNotices]: ...


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

    @property
    def msg_maker(self) -> NoticeMsgMaker:
        """
        Implementations should pass this on when generating a file notices
        """

    def known_locations(self) -> Iterator[pathlib.Path]:
        """
        Yield locations that have associated file notices
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

    def generate_notices_for_location(
        self, location: pathlib.Path, *, msg_maker: NoticeMsgMaker | None = None
    ) -> FileNotices:
        """
        Return a file notices for this location

        Implementations should not modify this ProgramNotices
        """


class Expectations(Protocol[T_Scenario]):
    """
    This objects knows what to expect from running the static type checker
    """

    def check(self, *, notice_checker: NoticeChecker[T_Scenario]) -> None:
        """
        Used to check the result against these expectations
        """


class ExpectationsMaker(Protocol[T_Scenario]):
    """
    Callable that creates an Expectations object
    """

    def __call__(self) -> Expectations[T_Scenario]: ...


class ExpectationsSetup(Protocol[T_Scenario]):
    """
    Used to setup an expectations maker
    """

    def __call__(self, *, options: RunOptions[T_Scenario]) -> ExpectationsMaker[T_Scenario]: ...


class Expects(Protocol):
    """
    Holds boolean expectations
    """

    failure: bool
    """
    Whether the assertions in the test are expected to fail
    """

    daemon_restarted: bool
    """
    Whether a daemon restart is expected
    """


class Scenario(Protocol):
    """
    Used to hold relevant information for running and testing a type checker run.

    This object is overridden to provide a mechanism for stringing custom data throughout
    all the other objects.

    A default implementation is provided by ``pytest_typing_runner.Scenario``

    The ``typing_scenario_maker`` fixture can be defined to return the exact concrete
    implementation to use for a particular scope.
    """

    @property
    def expects(self) -> Expects:
        """
        Boolean expectations
        """

    @property
    def root_dir(self) -> pathlib.Path:
        """
        The root directory for all files in the scenario
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
    def default_program_runner_maker(self) -> ProgramRunnerMaker[T_Scenario]:
        """
        Default constructor for making a program runner
        """

    @property
    def cleaners(self) -> RunCleaners:
        """
        An object to register cleanup functions for the end of the run
        """

    def execute_static_checking(
        self, *, options: RunOptions[T_Scenario]
    ) -> NoticeChecker[T_Scenario]:
        """
        Called to use the run options to run a type checker and get a result
        """

    def run_and_check(
        self, *, options: RunOptions[T_Scenario], setup_expectations: ExpectationsSetup[T_Scenario]
    ) -> None:
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

    def file_modification(self, path: str, content: str | None) -> None:
        """
        Used to modify a file for the scenario and record it on the runs
        """

    def normalise_program_runner_notice(
        self, options: RunOptions[T_Scenario], notice: ProgramNotice, /
    ) -> ProgramNotice:
        """
        Used to normalise each notice parsed from the output of the program runner
        """

    def generate_program_notices(
        self, *, msg_maker: NoticeMsgMaker | None = None
    ) -> ProgramNotices:
        """
        Return an object that satisfies an empty :protocol:`ProgramNotices`
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
        scenario_runs_maker: ScenarioRunsMaker[T_Scenario],
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

    def notices(self, *, into: FileNotices) -> FileNotices | None:
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
    P_ScenarioRunsMaker = ScenarioRunsMaker[P_Scenario]
    P_ScenarioFileMaker = ScenarioFileMaker[P_ScenarioFile]
    P_ExpectationsMaker = ExpectationsMaker[P_Scenario]
    P_ExpectationsSetup = ExpectationsSetup[P_Scenario]
    P_ScenarioRunnerMaker = ScenarioRunnerMaker[P_Scenario]

    P_Severity = Severity
    P_FileNotices = FileNotices
    P_LineNotices = LineNotices
    P_ProgramNotice = ProgramNotice
    P_ProgramNotices = ProgramNotices
    P_FileNoticesParser = FileNoticesParser
    P_FileNoticesChanger = FileNoticesChanger
    P_LineNoticesChanger = FileNoticesChanger
    P_ProgramNoticeChanger = ProgramNoticeChanger
    P_ProgramNoticesChanger = ProgramNoticesChanger

    P_NoticeMsg = NoticeMsg
    P_NoticeMsgMaker = NoticeMsgMaker
    P_NoticeMsgMakerMap = NoticeMsgMakerMap

    P_DiffNotices = DiffNotices
    P_DiffFileNotices = DiffFileNotices

    P_RunOptions = RunOptions[P_Scenario]
    P_NoticeChecker = NoticeChecker[P_Scenario]
    P_ProgramRunner = ProgramRunner[P_Scenario]
    P_RunOptionsModify = RunOptionsModify[P_Scenario]
    P_ProgramRunnerMaker = ProgramRunnerMaker[P_Scenario]

    P_RunResult = RunResult
    P_RunCleaner = RunCleaner
    P_RunCleaners = RunCleaners
    P_FileModifier = FileModifier
    P_RunnerConfig = RunnerConfig
    P_ProgramRunnerChooser = ProgramRunnerChooser

    P_Strategy = Strategy
    P_StrategyMaker = StrategyMaker
    P_StrategyRegistry = StrategyRegistry

    _FM: P_FileModifier = cast(P_ScenarioRunner, None).file_modification
