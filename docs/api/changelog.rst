.. _changelog:

Changelog
---------

.. _release-0.5.1:

0.5.1 - TBD
    * Made FileParser do mypy style inline comments by default
    * It is now possible to create notices for comparison using regexes and globs.
    * Added a ``typing_scenario_root_dir`` fixture for configurating where all the files
      in the scenario end up.
    * Change the ``RunnerConfig`` have the default strategy rather than only a way
      of creating the default strategy.
    * Order entry points when doing discovery of the typing strategies available to the
      CLI options.

.. _release-0.5.0:

0.5.0 - 29th August 2024
    * Initial release as a fork and evolution of the ``pytest-mypy-plugins``
      package.
