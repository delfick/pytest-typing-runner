import dataclasses
import functools
import pathlib
import textwrap

import pytest
from pytest_typing_runner_test_driver import matchers, stubs

from pytest_typing_runner import (
    builder,
    expectations,
    file_changer,
    notice_changers,
    notices,
    parse,
    protocols,
    runner,
    scenarios,
)


class TestScenarioFile:
    def test_it_has_attributes(self, tmp_path: pathlib.Path) -> None:
        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            return (content, into)

        def file_modification(*, path: str, content: str | None) -> None:
            pass

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert scenario_file.path == "one"
        assert scenario_file.root_dir is tmp_path
        assert scenario_file.file_parser is file_parser
        assert scenario_file.file_modification is file_modification

    def test_it_can_set_contents(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []
        original = "original content!"
        modified = "modified content!"

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.set(original) is scenario_file
        assert called == [("parse", original), ("modify", "one", modified)]

    def test_it_can_delete_contents(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            raise AssertionError("file parser shouldn't be used")

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.set(None) is scenario_file
        assert called == [("modify", "one", None)]

    def test_it_can_set_with_alternative_parser(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []

        original = "original content"
        modified = "changed content"

        def file_parser1(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            raise AssertionError("file parser shouldn't be used")

        def file_parser2(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse2", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser1,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.override_file_parser(file_parser2) is scenario_file
        assert scenario_file.set(original) is scenario_file
        assert called == [("parse2", original), ("modify", "one", modified)]

    def test_it_can_append_content(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []
        original = "original content!"
        extra = "extra content"
        modified = "modified content!"

        (tmp_path / "one").write_text(original)

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.append(extra) is scenario_file
        assert called == [("parse", f"{original}\n{extra}"), ("modify", "one", modified)]

    def test_it_can_append_content_with_different_dividier(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []
        original = "original content!"
        extra = "extra content"
        modified = "modified content!"

        (tmp_path / "one").write_text(original)

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.append(extra, divider="::") is scenario_file
        assert called == [("parse", f"{original}::{extra}"), ("modify", "one", modified)]

    def test_it_complains_if_appending_to_file_that_does_not_exist(
        self, tmp_path: pathlib.Path
    ) -> None:
        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            raise AssertionError("not called")

        def file_modification(*, path: str, content: str | None) -> None:
            raise AssertionError("not called")

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        with pytest.raises(file_changer.LocationDoesNotExist):
            scenario_file.append("extra")

    def test_it_can_be_told_to_not_complain_if_file_does_not_exist(
        self, tmp_path: pathlib.Path
    ) -> None:
        called: list[object] = []

        extra = "extra content"
        modified = "modified content!"

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert scenario_file.append(extra, must_exist=False) is scenario_file
        assert called == [("parse", extra), ("modify", "one", modified)]

    def test_it_can_append_with_alternative_parser(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []

        original = "original content"
        extra = "extra"
        modified = "changed content"

        (tmp_path / "one").write_text(original)

        def file_parser1(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            raise AssertionError("file parser shouldn't be used")

        def file_parser2(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse2", content))
            return (modified, into)

        def file_modification(*, path: str, content: str | None) -> None:
            called.append(("modify", path, content))

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser1,
            file_modification=file_modification,
        )

        assert called == []
        assert scenario_file.override_file_parser(file_parser2) is scenario_file
        assert scenario_file.append(extra) is scenario_file
        assert called == [("parse2", f"{original}\n{extra}"), ("modify", "one", modified)]

    def test_it_uses_parser_to_get_notices_with_expect_overrides(
        self, tmp_path: pathlib.Path
    ) -> None:
        called: list[object] = []

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content, into))
            return (
                content,
                notice_changers.ModifyLine(
                    name_or_line=2,
                    line_must_exist=False,
                    change=notice_changers.AppendToLine(
                        notices_maker=lambda ln: [ln.generate_notice(msg="n1")]
                    ),
                )(into),
            )

        def file_modification(*, path: str, content: str | None) -> None:
            raise AssertionError("not used")

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        assert called == []
        location = tmp_path / "one"
        into = notices.ProgramNotices().generate_notices_for_location(location)
        (tmp_path / "one").write_text("one")
        file_notices = scenario_file.notices(into=into)
        assert called == [("parse", "one", into)]
        assert list(file_notices or []) == [
            matchers.MatchNote(location=location, line_number=2, msg="n1")
        ]

        scenario_file.expect(
            notices.AddErrors(name="a", errors=[("arg-type", "e1"), ("arg-type", "a2")]),
            notices.AddNotes(name="b", notes=["n2"]),
        )

        called.clear()
        into2 = into.set_name("a", 50).set_name("b", 42)
        file_notices = scenario_file.notices(into=into2)
        assert called == [("parse", "one", into2)]
        assert sorted(file_notices or []) == [
            matchers.MatchNote(location=location, line_number=2, msg="n1"),
            matchers.MatchNote(location=location, line_number=42, msg="n2"),
            matchers.MatchNotice(
                location=location,
                line_number=50,
                severity=notices.ErrorSeverity("arg-type"),
                msg="a2",
            ),
            matchers.MatchNotice(
                location=location,
                line_number=50,
                severity=notices.ErrorSeverity("arg-type"),
                msg="e1",
            ),
        ]

    def test_it_complains_if_parser_wants_to_change_file(self, tmp_path: pathlib.Path) -> None:
        called: list[object] = []

        def file_parser(
            content: str, /, *, into: protocols.FileNotices
        ) -> tuple[str, protocols.FileNotices]:
            called.append(("parse", content, into))
            return ("different", into)

        def file_modification(*, path: str, content: str | None) -> None:
            raise AssertionError("not used")

        scenario_file = builder.ScenarioFile(
            path="one",
            root_dir=tmp_path,
            file_parser=file_parser,
            file_modification=file_modification,
        )

        (tmp_path / "one").write_text("original")
        into = notices.ProgramNotices().generate_notices_for_location(tmp_path / "one")
        with pytest.raises(AssertionError) as e:
            scenario_file.notices(into=into)

        assert str(e.value) == "Contents of 'one' were not transformed when written to disk"


class TestUsingBuilder:
    class Builder(builder.ScenarioBuilder[scenarios.Scenario, builder.ScenarioFile]):
        pass

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ProgramRunner(stubs.StubRunner[protocols.T_Scenario]):
        options: protocols.RunOptions[protocols.T_Scenario]

        def run(self) -> protocols.NoticeChecker[protocols.T_Scenario]:
            success_out = textwrap.dedent("""
            main.py:3: note: Revealed type is "builtins.int"
            Success: no issues found in 2 source files
            """).strip()

            error_out = textwrap.dedent("""
            main.py:3: note: Revealed type is "builtins.int"
            main.py:7: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]
            Found 1 error in 1 file (checked 2 source files)
            """).strip()

            first_content = textwrap.dedent("""
            a: int = 1
            reveal_type(a)
            # ^ REVEAL ^ builtins.int
            """).strip()

            second_content = textwrap.dedent("""
            a: int = 1
            reveal_type(a)
            # ^ REVEAL ^ builtins.int


            a = "asdf"
            # ^ ERROR(assignment) ^ Incompatible types in assignment (expression has type "str", variable has type "int")
            """).strip()

            found = (self.options.cwd / "main.py").read_text().strip()
            if found == first_content:
                result = expectations.RunResult(exit_code=0, stderr="", stdout=success_out)
            elif found == second_content:
                result = expectations.RunResult(exit_code=1, stderr="", stdout=error_out)
            else:
                raise AssertionError(found)

            return runner.MypyChecker(result=result, runner=self)

        def short_display(self) -> str:
            return "stubrunner"

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class ScenarioRunner(scenarios.ScenarioRunner[scenarios.Scenario]):
        def determine_options(self) -> protocols.RunOptions[scenarios.Scenario]:
            options = super().determine_options()
            return options.clone(
                make_program_runner=stubs.StubProgramRunnerMaker[scenarios.Scenario](
                    runner_kls=TestUsingBuilder.ProgramRunner
                )
            )

    @pytest.fixture
    def typing_scenario_runner_maker(self) -> protocols.ScenarioRunnerMaker[scenarios.Scenario]:
        return self.ScenarioRunner.create

    @pytest.fixture
    def build(self, typing_scenario_runner: ScenarioRunner) -> Builder:
        return self.Builder(
            scenario_runner=typing_scenario_runner,
            scenario_file_maker=functools.partial(
                builder.ScenarioFile,
                file_parser=parse.FileContent().parse,
                file_modification=typing_scenario_runner.file_modification,
            ),
        )

    def test_things(self, build: Builder) -> None:
        @build.run_and_check_after
        def _() -> None:
            build.on("main.py").set(
                """
                a: int = 1
                # ^ REVEAL ^ builtins.int
                """
            )

        @build.run_and_check_after
        def _() -> None:
            build.expect_failure()
            build.on("main.py").append(
                """
                a = "asdf"
                # ^ ERROR(assignment) ^ Incompatible types in assignment (expression has type "str", variable has type "int")
                """
            )
