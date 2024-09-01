.. _parse:

Parsing content for notices
===========================

This plugin provides some helpers for parsing content for :ref:`notices <notices>`.

Parsing Mypy output
-------------------

.. autoclass:: pytest_typing_runner.parse.MypyOutput
    :members:

Parsing input content
---------------------

It can be tedious to create test content with expected notices that keep track
of which line number notices should be on. Especially when changing a test such
that all the line numbers suddenly change.

To make this easier, the plugin provides the ability to parse a file to find
extra comments that indicate where notices are expected.

To make this happen requires doing something like the following:

.. code-block:: python

    from pytest_typing_runner import parse, protocols

    file_notices: protocols.FileNotices = ...
    original: str = ...

    transformed, file_notices = parse.FileContent().parse(original, into=file_notices)

The idea being that when creating the files, the ``transformed`` is used to write
to the file, and when creating expectations, the ``file_notices`` are used to
say what notices are expected. And raise an error if the second parse creates
more transformations.

There are two forms this can take (both active in the default ``FileParser``)
as follows:

Per line instructions
+++++++++++++++++++++

For example:

.. code-block:: python

    01: a: int = 1
    02: model: type[Leader] = Follow1
    03: # ^ REVEAL[one] ^ wat
    04: # ^ ERROR(arg-type) ^ an error
    05: # ^ ERROR(arg-type) ^ more
    06: # ^ ERROR(assignment) ^ another
    07: 
    08: a: int = "asdf"
    09: # ^ ERROR(assignment) ^ other
    10: # ^ REVEAL ^ stuff
    11: # ^ NOTE ^ one
    12: # ^ NOTE ^ two
    13: # ^ NOTE ^ three
    14: # ^ ERROR(assignment) ^ another
    15: # ^ NOTE ^ four
    16:
    17: def other() -> None:
    18:     return 1
    19:     # ^ ERROR(var-annotated)<regex> ^ Need type Blah for "Stuff".+
    20:     # ^ NAME[hi] ^
    21:
    22: if True:
    23:     reveal_type(found)
    24:     # ^ ERROR(arg-type)[other] ^ hi
    25:     # ^ REVEAL[other] ^ asdf
    26:     # ^ REVEAL ^ asdf2
    27:     # ^ ERROR(arg-type)[other] ^ hi

In this example, we are using ``NAME``, ``ERROR``, ``WARNING``, ``REVEAL``
and ``NOTE`` instructions.

These match the form of:

``# ^ INSTRUCTION(error-type)[name]<match> ^ msg``

Where INSTRUCTION is one of:

* NAME
* REVEAL
* ERROR
* NOTE
* WARNING

And ``error-type`` is only valid for ``ERROR`` instructions.

The ``name`` is a way of registered a name for that line.

And ``match`` says how to compare ``msg`` in this notice to the ``msg``
in the notice that was received for this file and line.

The default ``match`` options are ``plain``, ``regex`` and ``glob``.

Where ``REVEAL`` notes are extra special in that they will change the line
such that it becomes a ``reveal_type(...)``

* If the line is already a ``reveal_type`` then it is not changed
* If the line is an assignment, a line is added that does a ``reveal_type`` on
  the assigned variable
* Otherwise the line is wrapped in a ``reveal_type(...)`` call at the
  appropriate level of indentation

So after transformation the above file becomes

.. code-block:: python

    01: a: int = 1
    02: model: type[Leader] = Follow1
    03: reveal_type(model)
    04: # ^ REVEAL[one] ^ wat
    05: # ^ ERROR(arg-type) ^ an error
    06: # ^ ERROR(arg-type) ^ more
    07: # ^ ERROR(assignment) ^ another
    08: 
    09: a: int = "asdf"
    10: # ^ ERROR(assignment) ^ other
    11: reveal_type(a)
    12: # ^ REVEAL ^ stuff
    13: # ^ NOTE ^ one
    14: # ^ NOTE ^ two
    15: # ^ NOTE ^ three
    16: # ^ ERROR(assignment) ^ another
    17: # ^ NOTE ^ four
    18:
    19: def other() -> None:
    20:     return 1
    21:     # ^ ERROR(var-annotated) ^ Need type Blah for "Stuff".+
    22:     # ^ NAME[hi] ^
    23:
    24: if True:
    25:     reveal_type(found)
    26:     # ^ ERROR(arg-type)[other] ^ hi
    27:     # ^ REVEAL[other] ^ asdf
    28:     # ^ REVEAL ^ asdf2
    29:     # ^ ERROR(arg-type)[other] ^ hi

And the following notices are expected:

.. code-block::

    03: severity=note:: Revealed type is "wat"
    03: severity=error[arg-type]:: an error
    03: severity=error[arg-type]:: more
    03: severity=error[assignment]:: another
    09: severity=error[assignment]:: other
    11: severity=note:: Revealed type is "stuff"
    11: severity=note:: one
    11: severity=note:: two
    11: severity=note:: three
    11: severity=error[assignment]:: another
    11: severity=note:: four
    20: severity=error[var-annotated]:: Need type Blah for "Stuff".+
    25: severity=error[arg-type]:: hi
    25: severity=note:: Revealed type is "asdf"
    25: severity=note:: Revealed type is "asdf2"
    25: severity=error[arg-type]:: hi

Mypy stubtest style
+++++++++++++++++++

For example:

.. code-block:: python

    01: a: int = 1
    02: model: type[Leader] = Follow1 
    03: reveal_type(model) # N: Revealed type is "one" # E: an error  [arg-type] # E: more  [arg-type] # E: another  [assignment]
    04: 
    05: a: int = "asdf" # E: other  [assignment]
    06: reveal_type(a) # N: Revealed type is "stuff" # N: one # N: two # N: three # E: another  [assignment] # N: four
    07:
    08: def other() -> None:
    09:     return 1 # E<regex>: Need type Blah for "Stuff".+  [var-annotated]
    10:
    11: if True:
    12:     reveal_type(found) # E: hi  [arg-type] # N: Revealed type is "asdf" # N: Revealed type is "asdf2" # E: hi  [arg-type]

Comments found on lines with preceding code will be split by un-escaped hashes
and be interpreted as a command if starts with ``# N:``, ``# E:`` or ``# W:``
In this example, we are using ``NAME``, ``ERROR``, ``REVEAL`` and ``NOTE``

An optional column number may also be provided after the action. For example
``# E:20``.

There may also be a ``<match>`` after the instruction. For example:
``# N<regex>: Revealed type is "[^"]+"`` where the string within the brackets
may be ``plain`` for plain equality check, ``regex`` for using the ``msg`` as
a regular expression, or ``glob`` for using the ``msg`` as a glob.

The rest of the comment till the next un-escaped hash will be considered the
message for the notice. The ``E`` instruction will also look for the
``[error-type]`` at the end of the message.

And the following notices are expected:

.. code-block::

    03: severity=note:: Revealed type is "wat"
    03: severity=error[arg-type]:: an error
    03: severity=error[arg-type]:: more
    03: severity=error[assignment]:: another
    05: severity=error[assignment]:: other
    06: severity=note:: Revealed type is "stuff"
    06: severity=note:: one
    06: severity=note:: two
    06: severity=note:: three
    06: severity=error[assignment]:: another
    06: severity=note:: four
    09: severity=error[var-annotated]:: Need type Blah for "Stuff".+
    12: severity=error[arg-type]:: hi
    12: severity=note:: Revealed type is "asdf"
    12: severity=note:: Revealed type is "asdf2"
    12: severity=error[arg-type]:: hi

API for parsing input content
-----------------------------

.. automodule:: pytest_typing_runner.parse.errors
   :members:
   :member-order: bysource

.. automodule:: pytest_typing_runner.parse.protocols
   :members:
   :member-order: bysource

.. automodule:: pytest_typing_runner.parse.file_content
   :members:
   :member-order: bysource
