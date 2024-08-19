import pathlib
import textwrap

import pytest

from pytest_typing_runner.scenario import ScenarioRunner


class TestPlugin:
    def test_it_can_create_scenario_fixture(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, RunnerConfig, ScenarioRunner

            def test_has_scenario(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
                assert isinstance(typing_scenario_runner, ScenarioRunner)
                assert isinstance(typing_scenario_runner.scenario, Scenario)
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_it_can_change_class_used_for_scenario(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, ScenarioRunner, protocols
            import pytest


            def test_has_scenario(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
                assert typing_scenario_runner.scenario.__class__ is Scenario

            class TestOne:
                class MyScenario(Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_maker(self) -> protocols.ScenarioMaker[MyScenario]:
                    return self.MyScenario.create

                def test_has_scenario(self, typing_scenario_runner: "ScenarioRunner[TestOne.MyScenario]") -> None:
                    assert isinstance(typing_scenario_runner.scenario, self.MyScenario)

            class TestTwo:
                class MyScenario2(Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_maker(self) -> protocols.ScenarioMaker[MyScenario2]:
                    return self.MyScenario2.create

                def test_has_scenario(self, typing_scenario_runner: "ScenarioRunner[TestTwo.MyScenario2]") -> None:
                    assert isinstance(typing_scenario_runner.scenario, self.MyScenario2)

            def test_has_scenario_again(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
                assert typing_scenario_runner.scenario.__class__ is Scenario
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=4)

    def test_it_can_change_class_used_for_scenario_runner(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, ScenarioRunner, protocols
            import pytest


            def test_has_scenario(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
                assert typing_scenario_runner.__class__ is ScenarioRunner

            class TestOne:
                class MyScenarioRunner(ScenarioRunner[Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_runner_maker(self) -> protocols.ScenarioRunnerMaker[Scenario]:
                    return self.MyScenarioRunner

                def test_has_scenario(self, typing_scenario_runner: MyScenarioRunner) -> None:
                    assert isinstance(typing_scenario_runner, self.MyScenarioRunner)

            class TestTwo:
                class MyScenarioRunner2(ScenarioRunner[Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_runner_maker(self) -> type[MyScenarioRunner2]:
                    return self.MyScenarioRunner2

                def test_has_scenario(self, typing_scenario_runner: MyScenarioRunner2) -> None:
                    assert isinstance(typing_scenario_runner, self.MyScenarioRunner2)

            def test_has_scenario_again(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
                assert typing_scenario_runner.__class__ is ScenarioRunner
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
        from pytest_typing_runner import RunnerConfig, Scenario, ScenarioRunner
        from pytest_typing_runner import protocols
        import pathlib
        import pytest

        count: int = 0


        class MyScenarioRunner(ScenarioRunner[Scenario]):
            def __init__(
                self,
                *,
                config: RunnerConfig,
                root_dir: pathlib.Path,
                scenario_maker: protocols.ScenarioMaker[Scenario],
            ) -> None:
                super().__init__(config=config, root_dir=root_dir, scenario_maker=Scenario.create)
                global count
                count += 1
                self.count = count
                with open("{log}", 'a') as fle:
                    print("__init__", self.count, file=fle)

            def prepare_scenario(self) -> None:
                with open("{log}", 'a') as fle:
                    print("prepare", self.count, file=fle)

            def cleanup_scenario(self) -> None:
                with open("{log}", 'a') as fle:
                    print("cleanup", self.count, file=fle)

        @pytest.fixture()
        def typing_scenario_runner_maker() -> protocols.ScenarioRunnerMaker[Scenario]:
            return MyScenarioRunner
        """)

        pytester.makepyfile(f"""
        from pytest_typing_runner import Scenario, ScenarioRunner
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
        from pytest_typing_runner import Scenario, protocols, ScenarioRuns, ScenarioRunner
        from collections.abc import Iterator
        import dataclasses
        import pathlib
        import pytest


        @dataclasses.dataclass(frozen=True, kw_only=True)
        class Runs(ScenarioRuns):
            _lines: list[str] = dataclasses.field(init=False, default_factory=list)

            @property
            def has_runs(self) -> bool:
                return bool(self._lines)

            def for_report(self) -> Iterator[str]:
                yield from self._lines

            def add(self, *lines: str) -> None: 
                self._lines.extend(lines)


        class MyScenarioRunner(ScenarioRunner[Scenario]):
            def create_scenario_runs(self) -> protocols.ScenarioRuns[Scenario]:
                return Runs(scenario=self.scenario)

        @pytest.fixture()
        def typing_scenario_runner_maker() -> protocols.ScenarioRunnerMaker[Scenario]:
            return MyScenarioRunner
        """)

        pytester.makepyfile("""
        from pytest_typing_runner import ScenarioRunner, Scenario
        import pytest

        Scenario = ScenarioRunner[Scenario]


        def test_one(typing_scenario_runner: ScenarioRunner) -> None:
            typing_scenario_runner.runs.add("one", "two", "three")
            raise AssertionError("NO")

        class TestOne:
            def test_two(self, typing_scenario_runner: ScenarioRunner) -> None:
                typing_scenario_runner.runs.add("four", "five")

        class TestTwo:
            def test_three(self) -> None:
                raise AssertionError("No")

            class TestThree:
                def test_four(self, typing_scenario_runner: ScenarioRunner) -> None:
                    typing_scenario_runner.runs.add("six", "seven")
                    raise AssertionError("NO")

        def test_five(typing_scenario_runner: Scenario) -> None:
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
                        assert isinstance(val, ScenarioRunner)
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
