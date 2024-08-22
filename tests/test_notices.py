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


class TestLineNotices:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert line_notices.location == tmp_path
        assert line_notices.line_number == 2

        assert not line_notices.has_notices
        assert list(line_notices) == []

    def test_it_knows_if_it_can_have_notices(self, tmp_path: pathlib.Path) -> None:
        line_notices: protocols.LineNotices | None = notices.LineNotices(
            location=tmp_path, line_number=2
        )
        assert line_notices is not None
        assert not line_notices.has_notices
        n1 = line_notices.generate_notice()
        n2 = line_notices.generate_notice()
        assert not line_notices.has_notices

        copy = line_notices.set_notices([n1, n2])
        assert copy is not None
        assert not line_notices.has_notices
        assert list(line_notices) == []

        assert copy.has_notices
        assert list(copy) == [n1, n2]

    def test_it_can_ignore_adding_None_notices(self, tmp_path: pathlib.Path) -> None:
        line_notices: protocols.LineNotices | None = notices.LineNotices(
            location=tmp_path, line_number=2
        )
        assert line_notices is not None
        assert not line_notices.has_notices
        n1 = line_notices.generate_notice()
        n2 = line_notices.generate_notice()
        assert not line_notices.has_notices

        line_notices = line_notices.set_notices([n1, n2])
        assert line_notices is not None
        assert line_notices.has_notices
        assert list(line_notices) == [n1, n2]

        line_notices = line_notices.set_notices([n1, None])
        assert line_notices is not None
        assert line_notices.has_notices
        assert list(line_notices) == [n1]

    def test_it_can_become_empty(self, tmp_path: pathlib.Path) -> None:
        line_notices: protocols.LineNotices | None = notices.LineNotices(
            location=tmp_path, line_number=2
        )
        assert line_notices is not None
        assert not line_notices.has_notices
        n1 = line_notices.generate_notice()
        n2 = line_notices.generate_notice()
        assert not line_notices.has_notices

        line_notices = line_notices.set_notices([n1, n2])
        assert line_notices is not None
        assert line_notices.has_notices
        assert list(line_notices) == [n1, n2]

        deleted = line_notices.set_notices([None, None])
        assert deleted is None

        emptied = line_notices.set_notices([None, None], allow_empty=True)
        assert emptied is not None
        assert not emptied.has_notices
        assert list(emptied) == []

    def test_it_can_generate_a_program_notice(self, tmp_path: pathlib.Path) -> None:
        line_notices = notices.LineNotices(location=tmp_path, line_number=2)

        n1 = line_notices.generate_notice()
        assert n1.location == tmp_path
        assert n1.line_number == 2
        assert n1.severity == notices.NoteSeverity()
        assert n1.msg == ""
        assert n1.col is None

        n2 = line_notices.generate_notice(severity=notices.ErrorSeverity(error_type="arg-type"))
        assert n2.location == tmp_path
        assert n2.line_number == 2
        assert n2.severity == notices.ErrorSeverity(error_type="arg-type")
        assert n2.msg == ""
        assert n2.col is None

        n3 = line_notices.generate_notice(msg="other")
        assert n3.location == tmp_path
        assert n3.line_number == 2
        assert n3.severity == notices.NoteSeverity()
        assert n3.msg == "other"
        assert n3.col is None


class TestFileNotices:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        assert file_notices.location == tmp_path
        assert not file_notices.has_notices
        assert list(file_notices) == []

    def test_it_can_be_given_notices(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice()
        n2 = ln1.generate_notice()
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice()
        n4 = ln2.generate_notice()
        ln2 = ln2.set_notices([n3, n4], allow_empty=True)

        copy = file_notices.set_lines({2: ln1, 3: ln2})
        assert not file_notices.has_notices
        assert list(file_notices) == []
        assert copy.has_notices
        assert list(copy) == [n1, n2, n3, n4]

    def test_it_can_have_lines_removed(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice()
        n2 = ln1.generate_notice()
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice()
        n4 = ln2.generate_notice()
        ln2 = ln2.set_notices([n3, n4], allow_empty=True)

        file_notices = file_notices.set_lines({2: ln1, 3: ln2})
        assert file_notices.notices_at_line(2) == ln1
        assert file_notices.notices_at_line(3) == ln2

        file_notices = file_notices.set_lines({3: None})
        assert file_notices.notices_at_line(2) == ln1
        assert file_notices.notices_at_line(3) is None
        assert file_notices.has_notices
        assert list(file_notices) == [n1, n2]

        file_notices = file_notices.set_lines({2: None})
        assert not file_notices.has_notices
        assert file_notices.notices_at_line(2) is None
        assert list(file_notices) == []

    def test_it_can_set_and_keep_named_lines(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path).set_name("one", 2).set_name("two", 3)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice()
        n2 = ln1.generate_notice()
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice()
        n4 = ln2.generate_notice()
        ln2 = ln2.set_notices([n3, n4], allow_empty=True)

        assert file_notices.get_line_number("one") == 2
        assert file_notices.get_line_number("two") == 3
        assert not file_notices.has_notices
        assert list(file_notices) == []

        file_notices = file_notices.set_lines({2: ln1, 3: ln2})
        assert file_notices.has_notices
        assert list(file_notices) == [n1, n2, n3, n4]
        assert file_notices.notices_at_line(2) == ln1
        assert file_notices.notices_at_line(3) == ln2
        assert file_notices.get_line_number("one") == 2
        assert file_notices.get_line_number("two") == 3

        file_notices = file_notices.set_lines({2: None, 3: None})
        assert not file_notices.has_notices
        assert list(file_notices) == []
        assert file_notices.notices_at_line(2) is None
        assert file_notices.notices_at_line(3) is None
        assert file_notices.get_line_number("one") == 2
        assert file_notices.get_line_number("two") == 3

    def test_it_has_logic_for_finding_expected_named_lines(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path).set_name("one", 2).set_name("two", 3)

        assert file_notices.get_line_number(1) == 1
        assert file_notices.get_line_number(2) == 2
        assert file_notices.get_line_number("one") == 2
        assert file_notices.get_line_number("two") == 3
        assert file_notices.get_line_number("three") is None


class TestDiffFileNotices:
    def test_it_yields_sorted_by_line_number(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        ln1 = file_notices.generate_notices_for_line(1)
        na1 = ln1.generate_notice()
        nb1 = ln1.generate_notice()

        ln2 = file_notices.generate_notices_for_line(2)
        na2 = ln2.generate_notice()
        nb2 = ln2.generate_notice()
        na3 = ln2.generate_notice()
        nb3 = ln2.generate_notice()

        ln3 = file_notices.generate_notices_for_line(3)
        na4 = ln3.generate_notice()
        nb4 = ln3.generate_notice()
        na5 = ln3.generate_notice()
        nb5 = ln3.generate_notice()

        ln4 = file_notices.generate_notices_for_line(4)
        na6 = ln4.generate_notice()
        nb6 = ln4.generate_notice()

        diff_file_notices = notices.DiffFileNotices(
            by_line_number={
                3: ([na4, na5], [nb4, nb5]),
                2: ([na2, na3], [nb2, nb3]),
                1: ([na1], [nb1]),
                4: ([na6], [nb6]),
            }
        )

        assert list(diff_file_notices) == [
            (1, [na1], [nb1]),
            (2, [na2, na3], [nb2, nb3]),
            (3, [na4, na5], [nb4, nb5]),
            (4, [na6], [nb6]),
        ]


class TestDiffNotices:
    def test_it_yields_sorted_by_file(self, tmp_path: pathlib.Path) -> None:
        def make_notice(location: pathlib.Path) -> protocols.ProgramNotice:
            return notices.ProgramNotice(
                location=location,
                line_number=0,
                severity=notices.NoteSeverity(),
                col=None,
                msg="stuff",
            )

        l1 = tmp_path / "l1"
        n1 = make_notice(l1)
        dn1 = notices.DiffFileNotices(by_line_number={1: ([n1], [n1])})

        l2 = tmp_path / "l2"
        n2 = make_notice(l2)
        dn2 = notices.DiffFileNotices(by_line_number={2: ([n2], [n2])})

        l3 = tmp_path / "l3"
        n3 = make_notice(l3)
        dn3 = notices.DiffFileNotices(by_line_number={1: ([n3], [n3])})

        diff_notices = notices.DiffNotices(
            by_file={
                str(l3): dn3,
                str(l1): dn1,
                str(l2): dn2,
            },
        )
        assert list(diff_notices) == [
            (str(l1), dn1),
            (str(l2), dn2),
            (str(l3), dn3),
        ]
