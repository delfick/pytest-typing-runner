import argparse
import dataclasses
import importlib.metadata
import textwrap
from collections.abc import Callable, MutableMapping, Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import errors, protocols, runner


@dataclasses.dataclass(frozen=True, kw_only=True)
class NoStrategiesRegistered(errors.PyTestTypingRunnerException):
    """
    Raised when the registry is used with no registered strategies
    """


@dataclasses.dataclass(frozen=True, kw_only=True)
class Strategy:
    program_short: str
    program_runner_chooser: protocols.ProgramRunnerChooser


@dataclasses.dataclass
class StrategyRegistry:
    registry: MutableMapping[str, tuple[str, protocols.StrategyMaker]] = dataclasses.field(
        default_factory=dict
    )
    default_strategy: str | None = None

    @classmethod
    def discover(cls) -> Self:
        """
        Create a new registry and use entry points to discover register
        functions to populate the registry with.
        """
        registry = cls()

        for entry_point in importlib.metadata.entry_points(
            group="pytest_typing_runner_strategies"
        ):
            register = entry_point.load()
            register(registry)

        return registry

    def register(
        self,
        *,
        name: str,
        description: str,
        maker: protocols.StrategyMaker,
        make_default: bool = False,
    ) -> None:
        """
        Register a maker to a specific name
        """
        if make_default:
            self.set_default(name=name)
        self.registry[name] = (textwrap.dedent(description).strip(), maker)

    def remove_strategy(self, *, name: str) -> None:
        """
        Remove a strategy
        """
        if name in self.registry:
            del self.registry[name]

    def set_default(self, *, name: str) -> None:
        """
        Set the default strategy
        """
        self.default_strategy = name

    def get_strategy(self, *, name: str) -> tuple[str, protocols.StrategyMaker] | None:
        """
        Return the strategy for the provided name if one exists
        """
        return self.registry.get(name)

    @property
    def default(self) -> str:
        """
        Return the default strategy
        """
        if not self.registry:
            raise NoStrategiesRegistered()
        if self.default_strategy is not None:
            return self.default_strategy
        return sorted(self.registry)[0]

    @property
    def choices(self) -> list[str]:
        """
        Return known strategy names
        """
        return sorted(self.registry)

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class CLIOptions:
        str_to_maker: Callable[[str], protocols.StrategyMaker]
        help_text: str
        default: str
        choices: list[str]

    def cli_option_info(self) -> CLIOptions:
        def str_to_maker(name: str, /) -> protocols.StrategyMaker:
            got = self.get_strategy(name=name)
            if got is None:
                raise argparse.ArgumentTypeError(
                    f"Unknown strategy type: '{name}', available are {', '.join(self.choices)}"
                )
            return got[1]

        help_text: list[str] = ["The caching strategy used by the plugin"]
        for name in self.choices:
            got = self.get_strategy(name=name)
            if got is None:
                continue
            description, _ = got
            help_text.append("")
            help_text.append(name)
            for line in description.split("\n"):
                help_text.append(f"    {line}")

        return self.CLIOptions(
            str_to_maker=str_to_maker,
            help_text="\n".join(help_text),
            default=self.default,
            choices=self.choices,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class MypyChoice(Generic[protocols.T_Scenario]):
    default_args: Sequence[str]
    do_followups: bool
    same_process: bool
    is_daemon: bool = dataclasses.field(init=False, default=False)

    def __call__(
        self, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.ProgramRunner[protocols.T_Scenario]:
        if self.same_process:
            return runner.SameProcessMypyRunner(options=options)
        else:
            return runner.ExternalMypyRunner(options=options)


@dataclasses.dataclass(frozen=True, kw_only=True)
class DaemonMypyChoice(MypyChoice[protocols.T_Scenario]):
    is_daemon: bool = dataclasses.field(init=False, default=True)

    def __call__(
        self, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.ProgramRunner[protocols.T_Scenario]:
        return runner.ExternalDaemonMypyRunner(options=options)


def _make_no_incremental_strategy() -> protocols.Strategy:
    """
    - mypy is run only once for each run with --no-incremental
    """

    def choose(
        *, scenario: protocols.T_Scenario
    ) -> protocols.ProgramRunnerMaker[protocols.T_Scenario]:
        return MypyChoice(
            default_args=["--no-incremental"],
            do_followups=False,
            same_process=scenario.same_process,
        )

    if TYPE_CHECKING:
        _C: protocols.ProgramRunnerChooser = choose

    return Strategy(program_short="mypy", program_runner_chooser=choose)


def _make_incremental_strategy() -> protocols.Strategy:
    """
    - mypy is run twice for each run with --incremental.
    - First with an empty cache relative to the temporary directory
    - and again after that cache is made.
    """

    def choose(
        *, scenario: protocols.T_Scenario
    ) -> protocols.ProgramRunnerMaker[protocols.T_Scenario]:
        return MypyChoice(
            default_args=["--incremental"],
            do_followups=True,
            same_process=scenario.same_process,
        )

    if TYPE_CHECKING:
        _C: protocols.ProgramRunnerChooser = choose

    return Strategy(program_short="mypy", program_runner_chooser=choose)


def _make_dmypy_strategy() -> protocols.Strategy:
    """
    - A new dmypy is started and run twice for each run
    """

    def choose(
        *, scenario: protocols.T_Scenario
    ) -> protocols.ProgramRunnerMaker[protocols.T_Scenario]:
        return DaemonMypyChoice(
            default_args=["run", "--"],
            do_followups=True,
            same_process=scenario.same_process,
        )

    if TYPE_CHECKING:
        _C: protocols.ProgramRunnerChooser = choose

    return Strategy(program_short="mypy", program_runner_chooser=choose)


def register_default_strategies(registry: protocols.StrategyRegistry, /) -> None:
    registry.register(
        name="MYPY_NO_INCREMENTAL",
        description=_make_no_incremental_strategy.__doc__ or "",
        maker=_make_no_incremental_strategy,
        make_default=True,
    )
    registry.register(
        name="MYPY_INCREMENTAL",
        description=_make_incremental_strategy.__doc__ or "",
        maker=_make_incremental_strategy,
    )
    registry.register(
        name="MYPY_DAEMON",
        description=_make_dmypy_strategy.__doc__ or "",
        maker=_make_dmypy_strategy,
    )


if TYPE_CHECKING:
    _SR: protocols.StrategyRegistry = cast(StrategyRegistry, None)
    _S: protocols.P_Strategy = cast(Strategy, None)
    _RDS: protocols.StrategyRegisterer = register_default_strategies
    _MC: protocols.P_ProgramRunnerMaker = cast(MypyChoice[protocols.P_Scenario], None)
    _DC: protocols.P_ProgramRunnerMaker = cast(DaemonMypyChoice[protocols.P_Scenario], None)