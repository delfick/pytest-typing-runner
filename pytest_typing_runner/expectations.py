import dataclasses
import itertools
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Generic, cast

from typing_extensions import Self

from . import errors, notices, protocols


@dataclasses.dataclass(kw_only=True)
class NoticesAreDifferent(errors.PyTestTypingRunnerException, AssertionError):
    difference: str

    def __str__(self) -> str:
        return self.difference


@dataclasses.dataclass(frozen=True, kw_only=True)
class RunResult:
    """
    Holds the result from running a type checker

    Implements :protocol:`pytest_typing_runner.protocols.RunResult`

    :param exit_code: The return code from running the type checker
    :param stdout: A string of the stdout from running the type checker
    :param stderr: A string of the stderr from running the type checker
    """

    exit_code: int
    stdout: str
    stderr: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class Expectations(Generic[protocols.T_Scenario]):
    """
    Used to check the result of running a type checker against some expectation.

    Implements :protocol:`pytest_typing_runner.protocols.Expectations`

    :param expect_fail: Whether we expect the run to have failed.
    :param expect_stderr: What we expect in the stderr
    :param expect_notices: The notices expected from running the type checker
    """

    expect_fail: bool = False
    expect_stderr: str = ""
    expect_notices: protocols.ProgramNotices = dataclasses.field(
        default_factory=notices.ProgramNotices
    )

    def check(self, *, notice_checker: protocols.NoticeChecker[protocols.T_Scenario]) -> None:
        """
        Used to pass in the epxected notices to the notice checker and the
        check the stderr and exit_code on the run result.

        :param notice_checker:
            The object that holds the run result, runner that was used, and the
            logic for checking the notices in the run result.
        :raises AssertionError: If stderr on the result is different than expected
        :raises AssertionError:
            If exit code is non zero when we don't expect fail or if the exit
            code is 0 when we do expect failure
        """
        notice_checker.check(self.expect_notices)

        result = notice_checker.result
        assert result.stderr == self.expect_stderr, (
            f"Expected stderr in result ({result.stderr}) to match expectations ({self.expect_stderr})"
        )
        if self.expect_fail:
            assert result.exit_code != 0, (
                f"Expected exit code from result ({result.exit_code}) to be non zero"
            )
        else:
            assert result.exit_code == 0, (
                f"Expected exit code from result ({result.exit_code}) to be zero"
            )

    @classmethod
    def setup_for_success(
        cls, *, options: protocols.RunOptions[protocols.T_Scenario]
    ) -> type[Self]:
        """
        Handy implementation of :protocol:`pytest_typing_runner.protocols.ExpectationsSetup`
        """
        return cls


def normalise_notices(
    notices: Sequence[protocols.ProgramNotice],
) -> Iterator[protocols.ProgramNotice]:
    """
    Used to split up notices that have multiline messages.

    So instead of

    ```
    severity=note:: one\ntwo\nthree
    ```

    We get

    ```
    severity=note:: one
    severity=note:: two
    severity=note:: three
    ```
    """
    for notice in sorted(notices):
        split = list(notice.msg.split_lines())
        if len(split) == 1:
            yield notice
        else:
            for msg in split:
                yield notice.clone(msg=msg)


def compare_notices(diff: protocols.DiffNotices) -> None:
    """
    Create a diff message and raise it inside an ``AssertionError`` if there is
    a difference present in the provided diff.
    """
    tick = "✓"
    cross = "✘"

    msg: list[str] = []
    different: bool = False

    for path, fdiff in diff:
        msg.append(f"> {path}")
        for line_number, left_notices, right_notices in fdiff:
            left_notices = list(normalise_notices(left_notices))
            right_notices = list(normalise_notices(right_notices))

            for_line: list[str | tuple[str, str]] = []

            for left, right in itertools.zip_longest(left_notices, right_notices):
                if left is None or right is None:
                    for_line.append(
                        (
                            "<NONE>" if left is None else left.display(),
                            "<NONE>" if right is None else right.display(),
                        )
                    )
                    continue

                if right.matches(left):
                    for_line.append(left.display())
                else:
                    for_line.append((left.display(), right.display()))

            prefix = "  | "
            line_check = tick if all(isinstance(m, str) for m in for_line) else cross
            if line_check == cross:
                different = True

            if len(for_line) == 1 and isinstance(for_line[0], str):
                msg.append(f"{prefix}{line_check} {line_number}:")
                msg[-1] = f"{msg[-1]} {for_line[0]}"
            else:
                msg.append(f"{prefix}{line_check} {line_number}:")
                for same_or_different in for_line:
                    if isinstance(same_or_different, str):
                        msg.append(f"{prefix}{tick} {same_or_different}")
                    else:
                        msg.append(f"{prefix}{cross} !! GOT  !! {same_or_different[0]}")
                        msg.append(f"{prefix}  !! WANT !! {same_or_different[1]}")

    if different:
        raise NoticesAreDifferent(difference="\n" + "\n".join(msg))


if TYPE_CHECKING:
    _RR: protocols.RunResult = cast(RunResult, None)

    _E: protocols.P_Expectations = cast(Expectations[protocols.P_Scenario], None)
    _SFS: protocols.P_ExpectationsSetup = Expectations[protocols.P_Scenario].setup_for_success
