.. _scenario:

The scenario
============

This plugin is designed around the idea that each test is a ``scenario`` where
some files are written, a type checker is run against those files, and the result
is checked.

The entire API the plugin exposed is generic to the
:protocol:`pytest_typing_runner.protocols.Scenario` such that projects may add
additional attributes/methods to the Scenario in their project and create
implementations of the other objects that reach out to those extra attributes
and methods.

The default implementation of this protocol is:

.. autoclass:: pytest_typing_runner.scenarios.Expects
    :members:
    :member-order: bysource

.. autoclass:: pytest_typing_runner.scenarios.Scenario
    :members:
    :member-order: bysource
