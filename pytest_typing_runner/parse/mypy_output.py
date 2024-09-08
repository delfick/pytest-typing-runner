import dataclasses
import pathlib
import re
from collections.abc import Sequence
from typing import ClassVar

from typing_extensions import Self

from .. import notice_changers, notices, protocols
from . import errors as parse_errors


class MypyOutput:
    """
    Helper class for parsing output from running Mypy.

    .. code-block:: python

        from pytest_typing_runner import parse, protocols
        from collections.abc import Sequence
        import pathlib


        empty_program_notices: protocols.ProgramNotices = ...

        # root_dir is going to be the path mypy was run in
        root_dir: pathlib.Path = ...

        # note that mypy output should be only the lines that have notes and errors
        # this means excluding blank lines and things like "Found 6 errors" or
        # messages from the daemon output.
        mypy_output: Sequence[str] = ...


        def normalise(notice: protocols.ProgramNotice, /) -> protocols.ProgramNotice | None:
            # opportunity to do any normalisation
            # for example if a version of a library is a particular version then
            # the message may be different
            # return notice as is if no change is required
            # return None to exclude a notice from the result
            return notice.clone(msg=notice.msg.replace("Type[", "type["))


        full_program_notices = parse.MypyOutput.parse(
            mypy_output,
            into=empty_program_notices,
            normalise=normalise,
            root_dir=root_dir,
        )
    """

    @dataclasses.dataclass(frozen=True, kw_only=True)
    class _LineMatch:
        filename: str
        line_number: int
        col: int | None
        severity: protocols.Severity
        msg: str

        mypy_output_line_regex: ClassVar[re.Pattern[str]] = re.compile(
            r"^(?P<filename>[^:]+):(?P<line_number>\d+)(:(?P<col>\d+))?: (?P<severity>[^:]+): (?P<msg>.+?)(\s+\[(?P<tag>[^\]]+)\])?$"
        )

        @classmethod
        def match(cls, line: str, /) -> Self | None:
            m = cls.mypy_output_line_regex.match(line.strip())
            if m is None:
                return None

            groups = m.groupdict()
            tag = "" if not groups["tag"] else groups["tag"].strip()
            severity_match = groups["severity"]

            severity: protocols.Severity
            if severity_match == "error":
                severity = notices.ErrorSeverity(tag)
            elif severity_match == "note":
                severity = notices.NoteSeverity()
            else:
                raise parse_errors.UnknownSeverity(line=line, severity=severity_match)

            return cls(
                filename=groups["filename"],
                line_number=int(groups["line_number"]),
                col=None if not (col := groups["col"]) else int(col),
                severity=severity,
                msg=groups["msg"].strip(),
            )

    @classmethod
    def parse(
        cls,
        lines: Sequence[str],
        /,
        *,
        normalise: protocols.ProgramNoticeChanger,
        into: protocols.ProgramNotices,
        root_dir: pathlib.Path,
    ) -> protocols.ProgramNotices:
        """
        Parse lines from mypy and return a copy of the provided program notices
        with the notices from the output.

        :param lines:
            Sequence of strings representing each line from mypy output. This assumes
            only the notes and errors from the output, with everything else including
            new lines already being stripped out.
        :param normalise:
            A :protocol:`pytest_typing_runner.protocols.ProgramNoticeChanger` that
            is used on every notice that is added
        :param into:
            The :protocol:`pytest_typing_runner.protocols.ProgramNotices` that the
            notices should be added to
        :param root_dir:
            The base directory that each path is added to to create the
            full location for each notice.
        :raises UnknownSeverity:
            For valid mypy lines with an invalid severity
        :raises InvalidMypyOutputLine:
            For any line that is not a valid mypy line.
        :returns:
            Copy of ``into`` with the notices found in the output.
        """
        program_notices = into

        for line in lines:
            if not line.strip():
                continue

            match = cls._LineMatch.match(line)
            if match is None:
                raise parse_errors.InvalidMypyOutputLine(line=line)

            program_notices = notice_changers.ModifyFile(
                location=root_dir / match.filename,
                must_exist=False,
                change=notice_changers.ModifyLine(
                    name_or_line=match.line_number,
                    line_must_exist=False,
                    change=notice_changers.AppendToLine(
                        notices_maker=lambda line_notices: [
                            normalise(
                                line_notices.generate_notice(
                                    severity=match.severity,
                                    msg=match.msg,
                                    msg_maker=notices.PlainMsg.create,
                                )
                            )
                        ]
                    ),
                ),
            )(program_notices)

        return program_notices
