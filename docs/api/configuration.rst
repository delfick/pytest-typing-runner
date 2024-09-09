.. _configuration:

Configuration
-------------

This plugin provides a ``typing_scenario_runner`` fixture that lets a test use a
``pytest_typing_runner.Scenario`` object to create a scenario to run a type checker
against.

There are several objects involved in this that allow customisation and a few
fixtures that provide the ability to inject these customized objects into different
parts of the pytest run.

There are these relevant protocols:

* :protocol:`pytest_typing_runner.protocols.RunnerConfig`
* :protocol:`pytest_typing_runner.protocols.ScenarioRuns`
* :protocol:`pytest_typing_runner.protocols.Scenario`
* :protocol:`pytest_typing_runner.protocols.ScenarioMaker`

There are a few pytest fixtures that can be overridden within any pytest scope
to change what concrete implementations get used:

.. code-block:: python

    from pytest_typing_runner import protocols
    import pytest


    @pytest.fixture
    def typing_runner_config(pytestconfig: pytest.Config) -> protocols.RunnerConfig:
        """
        Fixture to get a RunnerConfig with all the relevant settings from the pytest config

        Override this if you want a RunnerConfig that overrides the options provided
        by the command line
        """

.. code-block:: python

    from pytest_typing_runner import protocols, Scenario
    import pytest


    @pytest.fixture
    def typing_scenario_maker() -> protocols.ScenarioMaker[Scenario]:
        """
        Fixture to override the specific Scenario class that should be used.
        """

.. code-block:: python

    from pytest_typing_runner import protocols, Scenario
    import pytest


    @pytest.fixture
    def typing_scenario_runner_maker() -> protocols.ScenarioRunnerMaker[Scenario]:
        """
        Fixture to override what object may be used to drive the scenario

        Note that the default implementation of ``ScenarioRunner`` already satisfies
        the ``ScenarioRunnerMaker`` protocol, but ultimately that is what this fixture
        should return.

        It should also be typed in terms of what scenario class is active for that
        scope.

        Also note that pytest and this plugin does not provide any verification
        that the type annotations are correct and it's recommended to have
        protective assertions in complicated setups.
        """

.. code-block:: python
   
    import pytest
    import pathlib


    @pytest.fixture
    def typing_scenario_root_dir(tmp_path: pathlib.Path) -> pathlib.Path:
        """
        This sets the root path for all the files in the scenario.

        This example shows the default
        """
        return tmp_path / "scenario_root"

Example
+++++++

For example:

.. literalinclude:: ../../tests/test_skeleton_example.py
   :language: python
