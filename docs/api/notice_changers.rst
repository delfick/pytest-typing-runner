.. _notice_changers:

Notice Changers
===============

This plugin providers some helpers for modifying :ref:`notices <notices>` so
that the api of the notices themselves remains small.

These helpers are split into high level helpers available in
``pytest_typing_runner.notices`` and low level helpers available in
``pytest_typing_runner.notice_changers``.

High level changers
-------------------

.. autoclass:: pytest_typing_runner.notices.AddRevealedTypes
   :members: __call__

.. autoclass:: pytest_typing_runner.notices.AddErrors
   :members: __call__

.. autoclass:: pytest_typing_runner.notices.AddNotes
   :members: __call__

.. autoclass:: pytest_typing_runner.notices.RemoveFromRevealedType
   :members: __call__

Low level changers
------------------

.. automodule:: pytest_typing_runner.notice_changers
   :members:
   :member-order: bysource
