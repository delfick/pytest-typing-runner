.. _configuration:

Configuration
-------------

This plugin provides a ``typing_runner_scenario`` fixture that lets a test use a
``pytest_typing_runner.Scenario`` object to create a scenario to run a type checker
against.

There are several objects involved in this that allow customisation and a few
fixtures that provide the ability to inject these customized objects into different
parts of the pytest run.

There are these relevant protocols:

.. autoprotocol:: pytest_typing_runner.protocols.RunnerConfig

.. autoprotocol:: pytest_typing_runner.protocols.ScenarioHook
   :member-order: bysource

.. autoprotocol:: pytest_typing_runner.protocols.ScenarioRuns

.. autoprotocol:: pytest_typing_runner.protocols.Scenario

With two additional protocols to represent objects for creation:

.. autoprotocol:: pytest_typing_runner.protocols.ScenarioMaker

.. autoprotocol:: pytest_typing_runner.protocols.ScenarioHookMaker

There are four pytest fixtures that can be overridden within any pytest scope
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
    def typing_scenario_kls() -> type[Scenario]:
        """
        Fixture to override the specific Scenario class that should be used.
        """

.. code-block:: python

    from pytest_typing_runner import protocols, Scenario
    import pytest


    @pytest.fixture
    def typing_scenario_maker() -> protocols.ScenarioMaker[Scenario]:
        """
        Fixture to override what object may be used to create the scenario.

        Note that by default this will return whatever the ``typing_scenario_kls``
        fixture in the active scope returns. It is not mandatory to implement it
        like this, but it's useful if the class already satisfies the ScenarioMaker
        protocol.
        """

.. code-block:: python

    from pytest_typing_runner import protocols, Scenario, ScenarioHook
    import pytest


    @pytest.fixture
    def typing_scenario_hook_maker() -> protocols.ScenarioHookMaker[Scenario]:
        """
        Fixture to override what object may be used for scenario hooks.

        Note that the default implementation of ``ScenarioHook`` already satisfies
        the ``ScenarioHookMaker`` protocol, but ultimately that is what this fixture
        should return.

        It should also be typed in terms of what scenario class is active for that
        scope.

        Also note that pytest and this plugin does not provide any verification
        that the type annotations are correct and it's recommended to have
        protective assertions in complicated setups.
        """

Example
+++++++

For example:

.. literalinclude:: ../../tests/test_skeleton_example.py
   :language: python
