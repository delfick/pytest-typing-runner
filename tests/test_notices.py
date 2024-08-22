import dataclasses
import pathlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from pytest_typing_runner import notices, protocols


@dataclasses.dataclass
class OtherSeverity:
    display: str

    def __lt__(self, other: protocols.Severity) -> bool:
        return self.display < other.display


if TYPE_CHECKING:
    _OS: protocols.Severity = cast(OtherSeverity, None)


class TestNoteSeverity:
    def test_it_displays_note(self) -> None:
        sev = notices.NoteSeverity()
        assert sev.display == "note"

    def test_it_is_ordable(self) -> None:
        sev_c = OtherSeverity("c")
        sev_a = OtherSeverity("a")
        sev_z = OtherSeverity("z")
        sev_o = OtherSeverity("o")
        sev_n1 = notices.NoteSeverity()
        sev_n2 = notices.NoteSeverity()
        original: Sequence[protocols.Severity] = [sev_c, sev_n1, sev_a, sev_z, sev_n2, sev_o]
        assert sorted(original) == [sev_a, sev_c, sev_n1, sev_n2, sev_o, sev_z]

    def test_it_can_be_compared(self) -> None:
        assert notices.NoteSeverity() == notices.NoteSeverity()
        assert notices.NoteSeverity() == OtherSeverity("note")
        assert notices.NoteSeverity() != OtherSeverity("other")
        assert notices.NoteSeverity() != notices.ErrorSeverity(error_type="arg-type")


class TestErrorSeverity:
    def test_it_displays_error_with_error_type(self) -> None:
        assert notices.ErrorSeverity(error_type="arg-type").display == "error[arg-type]"
        assert notices.ErrorSeverity(error_type="assignment").display == "error[assignment]"

    def test_it_is_ordable(self) -> None:
        sev_c = OtherSeverity("c")
        sev_a = OtherSeverity("a")
        sev_z = OtherSeverity("z")
        sev_o = OtherSeverity("o")
        sev_e1 = notices.ErrorSeverity(error_type="misc")
        sev_e2 = notices.ErrorSeverity(error_type="")
        sev_e3 = notices.ErrorSeverity(error_type="arg-type")
        original: Sequence[protocols.Severity] = [
            sev_c,
            sev_e1,
            sev_e3,
            sev_a,
            sev_z,
            sev_e2,
            sev_o,
        ]
        assert sorted(original) == [sev_a, sev_c, sev_e2, sev_e3, sev_e1, sev_o, sev_z]

    def test_it_can_be_compared(self) -> None:
        assert notices.ErrorSeverity(error_type="arg-type") == notices.ErrorSeverity(
            error_type="arg-type"
        )
        assert notices.ErrorSeverity(error_type="arg-type") == OtherSeverity("error[arg-type]")

        assert notices.ErrorSeverity(error_type="assignment") != OtherSeverity("error[arg-type]")
        assert notices.ErrorSeverity(error_type="assignment") != notices.ErrorSeverity(
            error_type="arg-type"
        )

        assert notices.ErrorSeverity(error_type="assignment") != OtherSeverity("other[assignment]")

    def test_it_thinks_empty_error_type_is_wildcard(self) -> None:
        assert notices.ErrorSeverity(error_type="") == OtherSeverity("error")
        assert notices.ErrorSeverity(error_type="") == OtherSeverity("error[]")
        assert notices.ErrorSeverity(error_type="") == notices.ErrorSeverity(error_type="")
        assert notices.ErrorSeverity(error_type="") == OtherSeverity("error[arg-type]")
        assert notices.ErrorSeverity(error_type="") == notices.ErrorSeverity(error_type="arg-type")

        assert notices.ErrorSeverity(error_type="") != OtherSeverity("other")
        assert notices.ErrorSeverity(error_type="") != OtherSeverity("other[arg-type]")


class TestProgramNotice:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path, line_number=20, col=2, severity=notices.NoteSeverity(), msg="stuff"
        )
        assert notice.location is tmp_path
        assert notice.line_number == 20
        assert notice.col == 2
        assert notice.severity == notices.NoteSeverity()
        assert notice.msg == "stuff"

    def test_it_has_classmethod_for_getting_reveal_msg(self) -> None:
        assert notices.ProgramNotice.reveal_msg("things") == 'Revealed type is "things"'

    def test_it_can_clone(self, tmp_path: pathlib.Path) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path, line_number=20, col=2, severity=notices.NoteSeverity(), msg="stuff"
        )
        assert notice.clone(line_number=40) == notices.ProgramNotice(
            location=tmp_path, line_number=40, col=2, severity=notices.NoteSeverity(), msg="stuff"
        )
        assert notice.clone(col=None) == notices.ProgramNotice(
            location=tmp_path,
            line_number=20,
            col=None,
            severity=notices.NoteSeverity(),
            msg="stuff",
        )

        error_sev = notices.ErrorSeverity(error_type="arg-type")
        assert notice.clone(severity=error_sev) == notices.ProgramNotice(
            location=tmp_path, line_number=20, col=2, severity=error_sev, msg="stuff"
        )

        assert notice.clone(msg="other") == notices.ProgramNotice(
            location=tmp_path,
            line_number=20,
            col=2,
            severity=notices.NoteSeverity(),
            msg="other",
        )

        assert notice.clone(
            line_number=42, col=5, severity=OtherSeverity("blah"), msg="things"
        ) == notices.ProgramNotice(
            location=tmp_path,
            line_number=42,
            col=5,
            severity=OtherSeverity("blah"),
            msg="things",
        )

    def test_it_displays_when_no_col(self, tmp_path: pathlib.Path) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path,
            line_number=20,
            col=None,
            severity=notices.NoteSeverity(),
            msg="stuff",
        )
        assert notice.display() == "severity=note:: stuff"
        assert (
            notice.clone(severity=notices.ErrorSeverity(error_type="arg-type")).display()
            == "severity=error[arg-type]:: stuff"
        )

    def test_it_displays_when_have_col(self, tmp_path: pathlib.Path) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path,
            line_number=20,
            col=10,
            severity=notices.NoteSeverity(),
            msg="stuff",
        )
        assert notice.display() == "col=10 severity=note:: stuff"
        assert (
            notice.clone(severity=notices.ErrorSeverity(error_type="arg-type")).display()
            == "col=10 severity=error[arg-type]:: stuff"
        )

    def test_it_is_orderable(self, tmp_path: pathlib.Path) -> None:
        n1 = notices.ProgramNotice(
            location=tmp_path, line_number=20, col=10, severity=notices.NoteSeverity(), msg="zebra"
        )
        n2 = notices.ProgramNotice(
            location=tmp_path, line_number=20, col=None, severity=notices.NoteSeverity(), msg="b"
        )
        n3 = notices.ProgramNotice(
            location=tmp_path, line_number=40, col=None, severity=notices.NoteSeverity(), msg="a"
        )
        n4 = notices.ProgramNotice(
            location=tmp_path,
            line_number=20,
            col=None,
            severity=notices.ErrorSeverity(error_type="arg-type"),
            msg="c",
        )
        n5 = notices.ProgramNotice(
            location=tmp_path,
            line_number=10,
            col=None,
            severity=notices.ErrorSeverity(error_type="var-annotated"),
            msg="d",
        )

        original: Sequence[protocols.ProgramNotice] = [n1, n2, n3, n4, n5]
        assert sorted(original) == [n1, n4, n5, n3, n2]

    def test_it_can_match_against_another_program_notice(self, tmp_path: pathlib.Path) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path, line_number=20, col=10, severity=notices.NoteSeverity(), msg="zebra"
        )

        assert notice.matches(notice.clone())

        # column doesn't matter if left or right has no column
        assert notice.clone(col=None).matches(notice.clone(col=20))
        assert notice.clone(col=None).matches(notice.clone(col=None))
        assert notice.clone(col=2).matches(notice.clone(col=None))

        # column matters if left does have a column
        assert not notice.clone(col=2).matches(notice.clone(col=4))

        # Otherwise location, line_number, severity, msg all matter
        assert not notice.clone(line_number=19).matches(notice.clone(line_number=21))
        assert not notice.clone(severity=notices.NoteSeverity()).matches(
            notice.clone(severity=OtherSeverity("different"))
        )
        assert not notice.clone(msg="one").matches(notice.clone(msg="two"))
        assert not notice.matches(
            notices.ProgramNotice(
                location=tmp_path / "two",
                line_number=20,
                col=10,
                severity=notices.NoteSeverity(),
                msg="zebra",
            )
        )
