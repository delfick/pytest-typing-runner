import typing

import pytest

from pytest_typing_runner import Scenario, ScenarioHook, protocols


def test_it_works(typing_runner_scenario: Scenario) -> None:
    assert isinstance(typing_runner_scenario, Scenario)
    assert isinstance(typing_runner_scenario.scenario_hook, ScenarioHook)


class TestOther:
    class MyScenario(Scenario):
        def some_functionality(self) -> None: ...

    class MyScenarioHook(ScenarioHook[MyScenario]):
        def prepare_scenario(self) -> None:
            self.scenario.some_functionality()

    if typing.TYPE_CHECKING:
        # Let our type checker tell us if we satisfy the maker protocols
        _MS: protocols.ScenarioMaker[MyScenario] = MyScenario
        _MSH: protocols.ScenarioHookMaker[MyScenario] = MyScenarioHook

    @pytest.fixture
    def typing_scenario_kls(self) -> type[MyScenario]:
        return self.MyScenario

    @pytest.fixture
    def typing_scenario_hook_maker(self) -> protocols.ScenarioHookMaker[MyScenario]:
        return self.MyScenarioHook

    def test_it_works(self, typing_runner_scenario: MyScenario) -> None:
        assert isinstance(typing_runner_scenario, self.MyScenario)
        assert isinstance(typing_runner_scenario.scenario_hook, self.MyScenarioHook)
