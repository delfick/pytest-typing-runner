import typing

import pytest

from pytest_typing_runner import Scenario, ScenarioRunner, protocols


def test_it_works(typing_scenario_runner: ScenarioRunner[Scenario]) -> None:
    assert isinstance(typing_scenario_runner, ScenarioRunner)
    assert isinstance(typing_scenario_runner.scenario, Scenario)


class TestOther:
    class MyScenario(Scenario):
        info: int = 1

        def some_functionality(self) -> None:
            self.info = 2

    class MyScenarioRunner(ScenarioRunner[MyScenario]):
        def prepare_scenario(self) -> None:
            self.scenario.some_functionality()

    if typing.TYPE_CHECKING:
        # Let our type checker tell us if we satisfy the maker protocols
        _MS: protocols.ScenarioMaker[MyScenario] = MyScenario.create
        _MSH: protocols.ScenarioRunnerMaker[MyScenario] = MyScenarioRunner.create

    @pytest.fixture
    def typing_scenario_maker(self) -> protocols.ScenarioMaker[MyScenario]:
        return self.MyScenario.create

    @pytest.fixture
    def typing_scenario_runner_maker(self) -> protocols.ScenarioRunnerMaker[MyScenario]:
        return self.MyScenarioRunner.create

    def test_it_works(self, typing_scenario_runner: MyScenarioRunner) -> None:
        assert isinstance(typing_scenario_runner, ScenarioRunner)
        assert isinstance(typing_scenario_runner.scenario, self.MyScenario)

        assert typing_scenario_runner.scenario.info == 2
