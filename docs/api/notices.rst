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
object with two default implementations:

.. autoclass:: pytest_typing_runner.notices.NoteSeverity

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
