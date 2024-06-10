.. _installation:

Installation
------------

The plugin can be found on pypi as ``pytest-typing-runner`` and can be installed
as part of a project's dependencies.

Being installed is enough for a ``pytest`` run to see and activate the plugin.

The plugin will create several additional options for pytest:

``--typing-same-process``
    This will make the type checker run within the same process as pytest. This is only
    recommended for local runs when it's desirable to set breakpoints in the
    code being tested. Without this, it is recommended to instead use
    something like the ``remote-pdb`` package that can be found on pypi.

    Note that this option will throw an error if combined with a typing strategy that
    cannot be run in the same process as the pytest run.

``--typing-strategy``
    This will set which type checker will be used and how it's used.

    MYPY_INCREMENTAL
        Runs mypy with it's ``--incremental`` cache. Will also mean that everytime mypy runs,
        it will run first with no cache and then again with the cache that was
        created (and only once for each subsequent run in a test).

    MYPY_NO_INCREMENTAL
        Runs mypy with it's ``--no-incremental`` option turning off the cache and will not
        perform followup runs.

    MYPY_DAEMON
        Runs the mypy daemon and will do a followup run on the first run for each test.
