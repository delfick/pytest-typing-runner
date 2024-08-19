from collections.abc import Sequence

from . import expectations, protocols


def interpret_mypy_output(
    scenario: protocols.T_Scenario,
    options: protocols.RunOptions[protocols.T_Scenario],
    lines: Sequence[str],
) -> protocols.ProgramNotices:
    # TODO: interpret mypy output
    return expectations.ProgramNotices(notices={})


def compare_notices(diff: protocols.DiffNotices) -> None:
    # TODO: raise error if different
    return None
