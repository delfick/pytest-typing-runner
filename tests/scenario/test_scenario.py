import pathlib

import pytest
from pytest_typing_runner_test_driver.stubs import StubRunnerConfig

from pytest_typing_runner import Scenario


class TestScenario:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        scenario = Scenario(root_dir=tmp_path, same_process=False)
        assert scenario.root_dir == tmp_path
        assert scenario.same_process is False
        assert not scenario.expects.failure
        assert not scenario.expects.daemon_restarted
        assert scenario.check_paths == ["."]

    @pytest.mark.parametrize("same_process", [False, True])
    def test_it_has_a_create_classmethod(self, same_process: bool, tmp_path: pathlib.Path) -> None:
        config = StubRunnerConfig(same_process=same_process)
        scenario = Scenario.create(config, tmp_path)
        # same_process comes from config
        assert scenario.same_process == same_process

        # root_dir comes from create method
        assert scenario.root_dir == tmp_path

        # Rest is defaults
        assert not scenario.expects.failure
        assert not scenario.expects.daemon_restarted
        assert scenario.check_paths == ["."]
