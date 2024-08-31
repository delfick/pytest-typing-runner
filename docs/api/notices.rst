.. _notices:

Notices
=======

The point of this plugin is ultimately to compare the output of some static
type checking tool against some known input and assert it matches some expected
output.

That output can be thought of as a sequence of what this plugin calls "notices"
that represent information about specific lines in specific files.

This plugin has a hierarchy to represent all those notices;

* :protocol:`pytest_typing_runner.protocols.ProgramNotices`
* has many :protocol:`pytest_typing_runner.protocols.FileNotices`
* has many :protocol:`pytest_typing_runner.protocols.LineNotices`
* has many :protocol:`pytest_typing_runner.protocols.ProgramNotice`

.. note::
   There are :ref:`notice_changers <notice_changers>` for modifying notices instead
   of directly accessing the api on the notices themselves

The :protocol:`pytest_typing_runner.protocols.ProgramNotice` has on it the file
location, the line number, an optional column number, a severity, and a message.

Severities are currently modelled as a :protocol:`pytest_typing_runner.protocols.Severity`
object with three default implementations:

.. autoclass:: pytest_typing_runner.notices.NoteSeverity

.. autoclass:: pytest_typing_runner.notices.WarningSeverity

.. autoclass:: pytest_typing_runner.notices.ErrorSeverity

These are the default implementations of the different layers of the notices:

.. autoclass:: pytest_typing_runner.notices.ProgramNotice
   :members:
   :member-order: bysource

.. autoclass:: pytest_typing_runner.notices.LineNotices(location: ~pathlib.Path, line_number: int)
   :members:
   :member-order: bysource

.. autoclass:: pytest_typing_runner.notices.FileNotices(location: ~pathlib.Path)
   :members:
   :member-order: bysource

.. autoclass:: pytest_typing_runner.notices.ProgramNotices()
   :members:
   :member-order: bysource

The ``msg`` on a ``ProgramNotice``
----------------------------------

The ``msg`` property on a :protocol:`pytest_typing_runner.notices.ProgramNotice`
is an object that has individual control over how it's compared to other messages.

This means that one ``msg`` may compare itself to another using a regular
expression, whereas one may compare itself using a glob. The most common will
be a plain equality check.

The default implementations are:

.. autoclass:: pytest_typing_runner.notices.PlainMsg
   :members:
   :member-order: bysource

.. autoclass:: pytest_typing_runner.notices.RegexMsg
   :members:
   :member-order: bysource

.. autoclass:: pytest_typing_runner.notices.GlobMsg
   :members:
   :member-order: bysource

Most things should be using
:protocol:`pytest_typing_runner.protocols.ScenarioRunner.generate_program_notices`
to create a :protocol:`pytest_typing_runner.protocols.ProgramNotices` which in
turn uses the ``default_msg_maker`` on the ``ScenarioRunner`` and so that's a
sensible place to change the default:

.. code-block:: python

    from pytest_typing_runner import scenarios, protocols
    import pytest


    class MyScenarioRunner(scenarios.ScenarioRunner[protocols.T_Scenario]):
        default_msg_maker: protocols.NoticeMsgMaker = notices.RegexMsg.create


    @pytest.fixture
    def typing_scenario_runner_maker(
        typing_scenario_maker: protocols.ScenarioMaker[protocols.T_Scenario],
    ) -> protocols.ScenarioRunnerMaker[protocols.T_Scenario]:
        return MyScenarioRunner.create

The ``msg_maker`` will be passed down from ``ProgramNotices`` to ``FileNotices``
to ``LineNotices`` when the ``generiate_*`` methods are used on these containers.

When ``generate_notice`` is used on a ``LineNotices`` it will use ``msg_maker``
if ``msg`` is passed in as a string. Otherwise it will use the ``msg`` as is.
