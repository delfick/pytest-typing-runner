import dataclasses
import functools
import pathlib
from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self, TypeVar

from . import expectations, file_changer, notices, protocols

T_CO_ScenarioFile = TypeVar(
    "T_CO_ScenarioFile", bound="ScenarioFile", default="ScenarioFile", covariant=True
)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioFile:
    path: str
    root_dir: pathlib.Path
    file_parser: protocols.FileNoticesParser
    file_modification: protocols.FileModifier

    _overrides: list[protocols.FileNoticesChanger] = dataclasses.field(
        init=False, default_factory=list
    )

    _file_parser_override: dict[None, protocols.FileNoticesParser] = dataclasses.field(
        init=False, default_factory=dict
    )

    def set(self, content: str | None) -> Self:
        self.file_modification(path=self.path, content=content)
        return self

    def append(self, content: str, *, divider: str = "\n", must_exist: bool = True) -> Self:
        self.file_modification(
            path=self.path,
            content=file_changer.FileAppender(
                root_dir=self.root_dir, path=self.path, extra_content=content
            ).after_append(divider=divider, must_exist=must_exist),
        )
        return self

    def expect(self, *instructions: protocols.FileNoticesChanger) -> Self:
        for instruction in instructions:
            self._overrides.append(instruction)
        return self

    def override_file_parser(self, parser: protocols.FileNoticesParser | None) -> Self:
        if parser is None:
            self._file_parser_override.clear()
        else:
            self._file_parser_override[None] = parser
        return self

    def notices(self) -> protocols.FileNotices | None:
        parser = self.file_parser
        if None in self._file_parser_override:
            parser = self._file_parser_override[None]

        file_notices = parser(location=self.root_dir / self.path)
        for instruction in self._overrides:
            changed = instruction(file_notices)
            if changed is None:
                file_notices = notices.FileNotices(location=file_notices.location)
            else:
                file_notices = changed

        if not file_notices.has_notices:
            return None

        return file_notices


@dataclasses.dataclass(frozen=True, kw_only=True)
class ScenarioBuilder(Generic[protocols.T_Scenario, T_CO_ScenarioFile]):
    file_changer: protocols.ScenarioFileMaker[T_CO_ScenarioFile]
    scenario_runner: protocols.ScenarioRunner[protocols.T_Scenario]

    _known_files: MutableMapping[str, T_CO_ScenarioFile] = dataclasses.field(
        init=False, default_factory=dict
    )

    def on(self, path: str) -> T_CO_ScenarioFile:
        if path not in self._known_files:
            self._known_files[path] = self.file_changer(
                path=path, root_dir=self.scenario_runner.scenario.root_dir
            )
        return self._known_files[path]

    def run_and_check(
        self,
        *,
        _change_expectations: Callable[[], None] | None = None,
    ) -> None:
        def make_expectations(
            scenario_runner: protocols.ScenarioRunner[protocols.T_Scenario],
            options: protocols.RunOptions[protocols.T_Scenario],
        ) -> protocols.Expectations[protocols.T_Scenario]:
            return self.make_expectations(
                scenario_runner=scenario_runner,
                options=options,
                change_expectations=_change_expectations,
            )

        return self.scenario_runner.run_and_check(make_expectations)

    def run_and_check_after(self, action: Callable[[], None]) -> None:
        self.run_and_check(_change_expectations=action)

    def make_expectations(
        self,
        *,
        scenario_runner: protocols.ScenarioRunner[protocols.T_Scenario],
        options: protocols.RunOptions[protocols.T_Scenario],
        change_expectations: Callable[[], None] | None,
    ) -> protocols.Expectations[protocols.T_Scenario]:
        if change_expectations is not None:
            change_expectations()

        return expectations.Expectations(
            options=options,
            expect_fail=scenario_runner.scenario.expect_fail,
            expect_stderr="",
            expect_notices=notices.ProgramNotices().set_files(
                {
                    scenario_runner.scenario.root_dir / path: known.notices()
                    for path, known in self._known_files.items()
                }
            ),
        )

    def daemon_should_not_restart(self) -> Self:
        self.scenario_runner.scenario.expect_dmypy_restarted = False
        return self

    def daemon_should_restart(self) -> Self:
        self.scenario_runner.scenario.expect_dmypy_restarted = True
        return self


if TYPE_CHECKING:
    _SC: protocols.P_ScenarioFile = cast(ScenarioFile, None)

    _SCM: protocols.P_ScenarioFileMaker = functools.partial(
        ScenarioFile,
        file_parser=cast(protocols.FileNoticesParser, None),
        file_modification=cast(protocols.FileModifier, None),
    )
