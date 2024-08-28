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
        parser = self.file_parser
        if None in self._file_parser_override:
            parser = self._file_parser_override[None]

        if content is not None:
            content, _ = parser(
                content, into=notices.FileNotices(location=self.root_dir / self.path)
            )

        self.file_modification(path=self.path, content=content)
        return self

    def append(self, content: str, *, divider: str = "\n", must_exist: bool = True) -> Self:
        return self.set(
            content=file_changer.FileAppender(
                root_dir=self.root_dir, path=self.path, extra_content=content
            ).after_append(divider=divider, must_exist=must_exist),
        )

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

    def notices(self, *, into: protocols.FileNotices) -> protocols.FileNotices | None:
        parser = self.file_parser
        file_notices = into
        if None in self._file_parser_override:
            parser = self._file_parser_override[None]

        location = self.root_dir / self.path
        original = location.read_text()
        replacement, file_notices = parser(original, into=file_notices)
        assert (
            replacement == original
        ), "Contents of {self.path} were not transformed when written to disk"

        for instruction in self._overrides:
            changed = instruction(file_notices)
            if changed is None:
                file_notices = into.clear(clear_names=True)
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
        def setup_expectations(
            *, options: protocols.RunOptions[protocols.T_Scenario]
        ) -> protocols.ExpectationsMaker[protocols.T_Scenario]:
            if _change_expectations is not None:
                _change_expectations()

            return functools.partial(self.make_expectations, options=options)

        return self.scenario_runner.run_and_check(setup_expectations)

    def run_and_check_after(self, action: Callable[[], None]) -> None:
        self.run_and_check(_change_expectations=action)

    def make_expectations(
        self, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> protocols.Expectations[protocols.T_Scenario]:
        root_dir = options.cwd
        program_notices = options.scenario_runner.generate_program_notices()

        return expectations.Expectations(
            expect_fail=self.scenario_runner.scenario.expects.failure,
            expect_stderr="",
            expect_notices=program_notices.set_files(
                {
                    (location := root_dir / path): known.notices(
                        into=program_notices.generate_notices_for_location(location)
                    )
                    for path, known in self._known_files.items()
                }
            ),
        )

    def expect_failure(self) -> Self:
        self.scenario_runner.scenario.expects.failure = True
        return self

    def expect_success(self) -> Self:
        self.scenario_runner.scenario.expects.failure = False
        return self

    def daemon_should_not_restart(self) -> Self:
        self.scenario_runner.scenario.expects.daemon_restarted = False
        return self

    def daemon_should_restart(self) -> Self:
        self.scenario_runner.scenario.expects.daemon_restarted = True
        return self


if TYPE_CHECKING:
    _SC: protocols.P_ScenarioFile = cast(ScenarioFile, None)

    _SCM: protocols.P_ScenarioFileMaker = functools.partial(
        ScenarioFile,
        file_parser=cast(protocols.FileNoticesParser, None),
        file_modification=cast(protocols.FileModifier, None),
    )
