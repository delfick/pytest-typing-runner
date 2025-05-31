.. _changelog:

Changelog
---------

.. _release-0.6.2:

0.6.1 - 31 May 2025
    * Removed python warnings about invalid escape sequences

.. _release-0.6.1:

0.6.1 - 27 October 2024
    * Made the errors not be frozen dataclasses. Being frozen dataclasses means pytest catching
      them would complain about not being able to set ``__traceback__`` on them

.. _release-0.6.0:

0.6.0 - 9 September 2024
    * Made FileParser do mypy style inline comments by default
    * It is now possible to create notices for comparison using regexes and globs.
    * Added a ``typing_scenario_root_dir`` fixture for configurating where all the files
      in the scenario end up.
    * Change the ``RunnerConfig`` have the default strategy rather than only a way
      of creating the default strategy.
    * Order entry points when doing discovery of the typing strategies available to the
      CLI options.
    * Ensure a current working directory can be depended on when using
      ``file_changers.BasicPythonAssignmentChanger`` regardless of whether the file being
      changed already exists or not.
    * Allow runners to modify the run options and pass that along in the notice checker.
    * The behaviour of ``scenario.expects.failure`` is now that this indicates the run is expected
      to fail assertions rather than only that the run is expected to exit with exit code of
      non zero
    * Make it possible for the builder to be given program notice changers so that followup runs
      can be given baseline notices to start from before extracting notices from known files and
      file level expectations.

.. _release-0.5.0:

0.5.0 - 29th August 2024
    * Initial release as a fork and evolution of the ``pytest-mypy-plugins``
      package.
