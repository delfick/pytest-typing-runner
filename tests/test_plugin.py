import pathlib
import textwrap

import pytest

from pytest_typing_runner import scenarios


class TestPlugin:
    def test_it_can_create_scenario_fixture(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import scenarios, protocols

            def test_has_scenario(typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
                assert isinstance(typing_scenario_runner, scenarios.ScenarioRunner)
                assert isinstance(typing_scenario_runner.scenario, scenarios.Scenario)
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_it_can_change_class_used_for_scenario(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import scenarios, protocols
            import dataclasses
            import pytest


            def test_has_scenario(typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
                assert typing_scenario_runner.scenario.__class__ is scenarios.Scenario

            class TestOne:
                @dataclasses.dataclass(frozen=True, kw_only=True)
                class MyScenario(scenarios.Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_maker(self) -> protocols.ScenarioMaker[MyScenario]:
                    return self.MyScenario.create

                def test_has_scenario(self, typing_scenario_runner: protocols.ScenarioRunner[MyScenario]) -> None:
                    assert isinstance(typing_scenario_runner.scenario, self.MyScenario)

            class TestTwo:
                @dataclasses.dataclass(frozen=True, kw_only=True)
                class MyScenario2(scenarios.Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_maker(self) -> protocols.ScenarioMaker[MyScenario2]:
                    return self.MyScenario2.create

                def test_has_scenario(self, typing_scenario_runner: "scenarios.ScenarioRunner[TestTwo.MyScenario2]") -> None:
                    assert isinstance(typing_scenario_runner.scenario, self.MyScenario2)

            def test_has_scenario_again(typing_scenario_runner: scenarios.ScenarioRunner[scenarios.Scenario]) -> None:
                assert typing_scenario_runner.scenario.__class__ is scenarios.Scenario
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=4)

    def test_it_can_change_class_used_for_scenario_runner(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import scenarios, protocols
            import dataclasses
            import pytest


            def test_has_scenario(typing_scenario_runner: scenarios.ScenarioRunner[scenarios.Scenario]) -> None:
                assert typing_scenario_runner.__class__ is scenarios.ScenarioRunner

            class TestOne:
                @dataclasses.dataclass(frozen=True, kw_only=True)
                class MyScenarioRunner(scenarios.ScenarioRunner[scenarios.Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_runner_maker(self) -> protocols.ScenarioRunnerMaker[scenarios.Scenario]:
                    return self.MyScenarioRunner.create

                def test_has_scenario(self, typing_scenario_runner: MyScenarioRunner) -> None:
                    assert isinstance(typing_scenario_runner, self.MyScenarioRunner)

            class TestTwo:
                @dataclasses.dataclass(frozen=True, kw_only=True)
                class MyScenarioRunner2(scenarios.ScenarioRunner[scenarios.Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_runner_maker(self) -> type[MyScenarioRunner2]:
                    return self.MyScenarioRunner2.create

                def test_has_scenario(self, typing_scenario_runner: MyScenarioRunner2) -> None:
                    assert isinstance(typing_scenario_runner, self.MyScenarioRunner2)

            def test_has_scenario_again(typing_scenario_runner: scenarios.ScenarioRunner[scenarios.Scenario]) -> None:
                assert typing_scenario_runner.__class__ is scenarios.ScenarioRunner
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=4)

    def test_it_calls_prepare_and_clean_on_extension_runner_for_each_scenario(
        self, pytester: pytest.Pytester, tmp_path: pathlib.Path
    ) -> None:
        log = tmp_path / "log"
        log.write_text("")

        pytester.makeconftest(f"""
        from pytest_typing_runner import scenarios, protocols
        import dataclasses
        import pathlib
        import pytest

        count: dict[None, int] = {{None: 0}}

        def next_count() -> int:
            count[None] += 1
            return count[None]

        @dataclasses.dataclass(frozen=True, kw_only=True)
        class MyScenarioRunner(scenarios.ScenarioRunner[scenarios.Scenario]):
            count: int = dataclasses.field(default_factory=next_count)

            def __post_init__(self) -> None:
                with open("{log}", 'a') as fle:
                    print("__init__", self.count, file=fle)

            def prepare_scenario(self) -> None:
                with open("{log}", 'a') as fle:
                    print("prepare", self.count, file=fle)

            def cleanup_scenario(self) -> None:
                with open("{log}", 'a') as fle:
                    print("cleanup", self.count, file=fle)

        @pytest.fixture()
        def typing_scenario_runner_maker() -> protocols.ScenarioRunnerMaker[scenarios.Scenario]:
            return MyScenarioRunner.create
        """)

        pytester.makepyfile(f"""
        from pytest_typing_runner import scenarios
        from conftest import MyScenarioRunner
        import pytest


        def test_one(typing_scenario_runner: MyScenarioRunner) -> None:
            with open("{log}", 'a') as fle:
                print("test_one", file=fle)

        class TestOne:
            def test_two(self, typing_scenario_runner: MyScenarioRunner) -> None:
                with open("{log}", 'a') as fle:
                    print("test_two", file=fle)

        class TestTwo:
            def test_three(self) -> None:
                assert True

            class TestThree:
                def test_four(self, typing_scenario_runner: MyScenarioRunner) -> None:
                    with open("{log}", 'a') as fle:
                        print("test_four", file=fle)

        def test_five(typing_scenario_runner: MyScenarioRunner) -> None:
            with open("{log}", 'a') as fle:
                print("test_five", file=fle)
        """)

        result = pytester.runpytest()
        result.assert_outcomes(passed=5)

        assert (
            log.read_text()
            == textwrap.dedent("""
            __init__ 1
            prepare 1
            test_one
            cleanup 1
            __init__ 2
            prepare 2
            test_two
            cleanup 2
            __init__ 3
            prepare 3
            test_four
            cleanup 3
            __init__ 4
            prepare 4
            test_five
            cleanup 4
            """).lstrip()
        )

    def test_it_adds_a_report_section_for_failed_tests(
        self, pytester: pytest.Pytester, tmp_path: pathlib.Path
    ) -> None:
        pytester.makeconftest("""
        from pytest_typing_runner import scenarios, protocols
        from collections.abc import Iterator
        import dataclasses
        import pathlib
        import pytest


        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Runs(scenarios.ScenarioRuns):
            _lines: list[str] = dataclasses.field(init=False, default_factory=list)

            @property
            def has_runs(self) -> bool:
                return bool(self._lines)

            def for_report(self) -> Iterator[str]:
                yield from self._lines

            def add(self, *lines: str) -> None: 
                self._lines.extend(lines)

        @pytest.fixture()
        def typing_scenario_runs_maker() -> protocols.ScenarioRunsMaker[scenarios.Scenario]:
            return Runs
        """)

        pytester.makepyfile("""
        from pytest_typing_runner import scenarios, protocols
        import pytest


        def test_one(typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
            typing_scenario_runner.runs.add("one", "two", "three")
            raise AssertionError("NO")

        class TestOne:
            def test_two(self, typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
                typing_scenario_runner.runs.add("four", "five")

        class TestTwo:
            def test_three(self) -> None:
                raise AssertionError("No")

            class TestThree:
                def test_four(self, typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
                    typing_scenario_runner.runs.add("six", "seven")
                    raise AssertionError("NO")

        def test_five(typing_scenario_runner: protocols.ScenarioRunner[scenarios.Scenario]) -> None:
            raise AssertionError("No")
        """)

        result = pytester.runpytest()
        result.assert_outcomes(failed=4, passed=1)

        reports = [
            report
            for report in result.reprec.getreports()  # type: ignore[attr-defined]
            if isinstance(report, pytest.TestReport) and report.when == "call"
        ]
        assert len(reports) == 5

        for report in reports:
            found: bool = False
            if not report.passed:
                for name, val in report.user_properties:
                    if name == "typing_runner":
                        assert isinstance(val, scenarios.ScenarioRunner)
                        found = True

                if not found:
                    assert (
                        report.nodeid
                        == "test_it_adds_a_report_section_for_failed_tests.py::TestTwo::test_three"
                    )
                else:
                    if (
                        report.nodeid
                        == "test_it_adds_a_report_section_for_failed_tests.py::test_one"
                    ):
                        assert report.sections == [("typing_runner", "one\ntwo\nthree")]
                    elif (
                        report.nodeid
                        == "test_it_adds_a_report_section_for_failed_tests.py::TestTwo::TestThree::test_four"
                    ):
                        assert report.sections == [("typing_runner", "six\nseven")]
                    elif (
                        report.nodeid
                        == "test_it_adds_a_report_section_for_failed_tests.py::test_five"
                    ):
                        assert report.sections == []
                    else:
                        raise AssertionError(f"No other tests should fail: {report.nodeid}")
            else:
                assert report.nodeid == (
                    "test_it_adds_a_report_section_for_failed_tests.py::TestOne::test_two"
                )
