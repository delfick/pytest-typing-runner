.. _file_changer:

The file changer helpers
========================

When a test fails pytest typing runner will add a pytest report section that
lists what files where changed/created/removed and the different commands that
were run to do static type checking, and their respective outputs.

To make that report know what files where changed requires all changes go through
the ``file_modification`` method on the scenario runner.

This is a function represented by :protocol:`pytest_typing_runner.protocols.FileModifier` 
and has a very simple interface that takes in the path to the file as a string
relative to the root directory of the scenario, and the contents to use (or ``None``
if the file should be deleted).

To add extra functionality around what kind of changes we want to make to files
there are some helpers in ``pytest_typing_runner.file_changers`` that are used
to determine what new content a file should have after a change.

.. automodule:: pytest_typing_runner.file_changers
   :members:
   :member-order: bysource
