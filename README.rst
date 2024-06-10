Pytest Typing Runner
====================

This is a plugin for pytest to assist in generating scenarios to run static
type checking against.

History
-------

This plugin comes out of a `fork`_ of the `pytest_mypy_plugins`_ pytest plugin
for writing tests that pytest can use to run mypy against sets of files.

The difference for this plugin is that it provides a pytest fixture to do work from
rather than exposing a ``yml`` interface for writing tests. It also allows for running
mypy multiple times in the same test with changes to the code being statically type
checked. And also has some different mechanisms for expressing the expected output
from mypy.

.. _pytest_mypy_plugins: https://pypi.org/project/pytest-mypy-plugins/
.. _fork: https://github.com/typeddjango/pytest-mypy-plugins/issues/144

Built Docs
----------

https://pytest-typing-runner.readthedocs.io
