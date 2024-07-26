import pathlib
import textwrap

import pytest

from pytest_typing_runner.scenario import ScenarioHook


class TestPlugin:
    def test_it_can_create_scenario_fixture(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, RunnerConfig, ScenarioHook, ScenarioRunner

            def test_has_scenario(typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                assert isinstance(typing_runner_scenario, ScenarioRunner)
                assert isinstance(typing_runner_scenario.scenario, Scenario)
                assert isinstance(typing_runner_scenario.scenario_hook, ScenarioHook)
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_it_can_change_class_used_for_scenario(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, ScenarioHookMaker, ScenarioRunner
            import pytest


            def test_has_scenario(typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                assert typing_runner_scenario.scenario.__class__ is Scenario

            class TestOne:
                class MyScenario(Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_kls(self) -> type[MyScenario]:
                    return self.MyScenario

                def test_has_scenario(self, typing_runner_scenario: "ScenarioRunner[TestOne.MyScenario]") -> None:
                    assert isinstance(typing_runner_scenario.scenario, self.MyScenario)

            class TestTwo:
                class MyScenario2(Scenario):
                    pass

                @pytest.fixture()
                def typing_scenario_kls(self) -> type[MyScenario2]:
                    return self.MyScenario2

                def test_has_scenario(self, typing_runner_scenario: "ScenarioRunner[TestTwo.MyScenario2]") -> None:
                    assert isinstance(typing_runner_scenario.scenario, self.MyScenario2)

            def test_has_scenario_again(typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                assert typing_runner_scenario.scenario.__class__ is Scenario
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=4)

    def test_it_can_change_class_used_for_scenario_hook(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            """
            from pytest_typing_runner import Scenario, ScenarioHook, ScenarioHookMaker, ScenarioRunner
            import pytest


            def test_has_scenario(typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                assert typing_runner_scenario.scenario_hook.__class__ is ScenarioHook

            class TestOne:
                class MyScenarioHook(ScenarioHook[Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_hook_maker(self) -> ScenarioHookMaker[Scenario]:
                    return self.MyScenarioHook

                def test_has_scenario(self, typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                    assert isinstance(typing_runner_scenario.scenario_hook, self.MyScenarioHook)

            class TestTwo:
                class MyScenarioHook2(ScenarioHook[Scenario]):
                    pass

                @pytest.fixture()
                def typing_scenario_hook_maker(self) -> type[MyScenarioHook2]:
                    return self.MyScenarioHook2

                def test_has_scenario(self, typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                    assert isinstance(typing_runner_scenario.scenario_hook, self.MyScenarioHook2)

            def test_has_scenario_again(typing_runner_scenario: ScenarioRunner[Scenario]) -> None:
                assert typing_runner_scenario.scenario_hook.__class__ is ScenarioHook
        """
        )

        result = pytester.runpytest()
        result.assert_outcomes(passed=4)

    def test_it_calls_prepare_and_clean_on_extension_hook_for_each_scenario(
        self, pytester: pytest.Pytester, tmp_path: pathlib.Path
    ) -> None:
        log = tmp_path / "log"
        log.write_text("")

        pytester.makeconftest(f"""
        from pytest_typing_runner import ScenarioHook, ScenarioHookMaker, RunnerConfig, ScenarioMaker, Scenario
        import pathlib
        import pytest

        count: int = 0


        class MyScenarioHook(ScenarioHook[Scenario]):
            def __init__(
                self,
                *,
                config: RunnerConfig,
                root_dir: pathlib.Path,
                Scenario: ScenarioMaker[Scenario],
            ) -> None:
                super().__init__(config=config, root_dir=root_dir, Scenario=Scenario)
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
        def typing_scenario_hook_maker() -> ScenarioHookMaker[Scenario]:
            return MyScenarioHook
        """)

        pytester.makepyfile(f"""
        from pytest_typing_runner import Scenario, ScenarioHook, ScenarioHookMaker, ScenarioRunner
        import pytest

        Runner = ScenarioRunner[Scenario]


        def test_one(typing_runner_scenario: Runner) -> None:
            with open("{log}", 'a') as fle:
                print("test_one", file=fle)

        class TestOne:
            def test_two(self, typing_runner_scenario: Runner) -> None:
                with open("{log}", 'a') as fle:
                    print("test_two", file=fle)

        class TestTwo:
            def test_three(self) -> None:
                assert True

            class TestThree:
                def test_four(self, typing_runner_scenario: Runner) -> None:
                    with open("{log}", 'a') as fle:
                        print("test_four", file=fle)

        def test_five(typing_runner_scenario: Runner) -> None:
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
        from pytest_typing_runner import Scenario, ScenarioHook, protocols, ScenarioRuns
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


        class MyScenarioHook(ScenarioHook[Scenario]):
            def create_scenario_runs(self) -> protocols.ScenarioRuns[Scenario]:
                return Runs(scenario=self.scenario)

        @pytest.fixture()
        def typing_scenario_hook_maker() -> protocols.ScenarioHookMaker[Scenario]:
            return MyScenarioHook
        """)

        pytester.makepyfile("""
        from pytest_typing_runner import ScenarioRunner, Scenario
        import pytest

        Scenario = ScenarioRunner[Scenario]


        def test_one(typing_runner_scenario: Scenario) -> None:
            typing_runner_scenario.scenario_hook.runs.add("one", "two", "three")
            raise AssertionError("NO")

        class TestOne:
            def test_two(self, typing_runner_scenario: Scenario) -> None:
                typing_runner_scenario.scenario_hook.runs.add("four", "five")

        class TestTwo:
            def test_three(self) -> None:
                raise AssertionError("No")

            class TestThree:
                def test_four(self, typing_runner_scenario: Scenario) -> None:
                    typing_runner_scenario.scenario_hook.runs.add("six", "seven")
                    raise AssertionError("NO")

        def test_five(typing_runner_scenario: Scenario) -> None:
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
                        assert isinstance(val, ScenarioHook)
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
