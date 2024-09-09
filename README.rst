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

Features
--------

* Provides pytest fixtures to help create scenarios for testing a type checker
* Each scenario is a set of files and a set of expectations around the behaviour
  of the type checker
* Scenarios may comprise of multiple runs of the type checker to check the
  behaviour of the type checker when changes are made against a warm cache
* Possible to run the same tests with different "strategies" where a strategy
  is a combination of specific type checker and default arguments
* Currently only supports ``mypy`` by default but should be possible to easily
  add more type checkers.
* Adds the ability to create files using a syntax for representing expectations
  in both the style used by ``mypy`` tests and a format introduced by this project
  that in some ways is a bit clearer and more expressive.

Built Docs
----------

https://pytest-typing-runner.readthedocs.io
