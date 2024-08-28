import dataclasses
import pathlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notice_changers, notices, protocols


@dataclasses.dataclass
class OtherSeverity:
    display: str

    def __lt__(self, other: protocols.Severity) -> bool:
        return self.display < other.display


if TYPE_CHECKING:
    _OS: protocols.Severity = cast(OtherSeverity, None)


@pytest.fixture
def file_notices(tmp_path: pathlib.Path) -> protocols.FileNotices:
    pm = notices.ProgramNotices()
    return pm.generate_notices_for_location(tmp_path)


@pytest.fixture
def line_notices(file_notices: protocols.FileNotices) -> protocols.LineNotices:
    return file_notices.generate_notices_for_line(10)


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
        assert notices.NoteSeverity() != notices.ErrorSeverity("arg-type")


class TestErrorSeverity:
    def test_it_displays_error_with_error_type(self) -> None:
        assert notices.ErrorSeverity("arg-type").display == "error[arg-type]"
        assert notices.ErrorSeverity("assignment").display == "error[assignment]"

    def test_it_is_ordable(self) -> None:
        sev_c = OtherSeverity("c")
        sev_a = OtherSeverity("a")
        sev_z = OtherSeverity("z")
        sev_o = OtherSeverity("o")
        sev_e1 = notices.ErrorSeverity("misc")
        sev_e2 = notices.ErrorSeverity("")
        sev_e3 = notices.ErrorSeverity("arg-type")
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
        assert notices.ErrorSeverity("arg-type") == notices.ErrorSeverity("arg-type")
        assert notices.ErrorSeverity("arg-type") == OtherSeverity("error[arg-type]")

        assert notices.ErrorSeverity("assignment") != OtherSeverity("error[arg-type]")
        assert notices.ErrorSeverity("assignment") != notices.ErrorSeverity("arg-type")

        assert notices.ErrorSeverity("assignment") != OtherSeverity("other[assignment]")

    def test_it_thinks_empty_error_type_is_wildcard(self) -> None:
        assert notices.ErrorSeverity("") == OtherSeverity("error")
        assert notices.ErrorSeverity("") == OtherSeverity("error[]")
        assert notices.ErrorSeverity("") == notices.ErrorSeverity("")
        assert notices.ErrorSeverity("") == OtherSeverity("error[arg-type]")
        assert notices.ErrorSeverity("") == notices.ErrorSeverity("arg-type")

        assert notices.ErrorSeverity("") != OtherSeverity("other")
        assert notices.ErrorSeverity("") != OtherSeverity("other[arg-type]")


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

    def test_it_has_ability_to_know_if_notice_is_a_type_reveal(
        self, tmp_path: pathlib.Path
    ) -> None:
        notice = notices.ProgramNotice(
            location=tmp_path, line_number=10, severity=notices.NoteSeverity(), msg="", col=None
        )

        assert not notice.is_type_reveal
        assert not notice.clone(severity=notices.ErrorSeverity("assignment")).is_type_reveal
        assert not notice.clone(
            severity=notices.ErrorSeverity("assignment"),
            msg=notices.ProgramNotice.reveal_msg("hello"),
        ).is_type_reveal
        assert not notice.clone(severity=notices.NoteSeverity(), msg="Revealed").is_type_reveal

        assert notice.clone(
            severity=notices.NoteSeverity(), msg='Revealed type is "hello"'
        ).is_type_reveal
        assert notice.clone(
            severity=notices.NoteSeverity(), msg=notices.ProgramNotice.reveal_msg("hi")
        ).is_type_reveal

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

        error_sev = notices.ErrorSeverity("arg-type")
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
            notice.clone(severity=notices.ErrorSeverity("arg-type")).display()
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
            notice.clone(severity=notices.ErrorSeverity("arg-type")).display()
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
            severity=notices.ErrorSeverity("arg-type"),
            msg="c",
        )
        n5 = notices.ProgramNotice(
            location=tmp_path,
            line_number=10,
            col=None,
            severity=notices.ErrorSeverity("var-annotated"),
            msg="d",
        )

        original: Sequence[protocols.ProgramNotice] = [n1, n3, n5, n4, n2]
        assert sorted(original) == [n5, n1, n4, n2, n3]

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
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
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
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
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
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
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

        n1 = line_notices.generate_notice(msg="n1")
        assert n1.location == tmp_path
        assert n1.line_number == 2
        assert n1.severity == notices.NoteSeverity()
        assert n1.msg == "n1"
        assert n1.col is None

        n2 = line_notices.generate_notice(msg="n2", severity=notices.ErrorSeverity("arg-type"))
        assert n2.location == tmp_path
        assert n2.line_number == 2
        assert n2.severity == notices.ErrorSeverity("arg-type")
        assert n2.msg == "n2"
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

    def test_it_can_get_known_names(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        assert file_notices.known_names == {}
        assert file_notices.set_name("one", 1).set_name("two", 2).known_names == {
            "one": 1,
            "two": 2,
        }

    def test_it_can_get_known_line_numbers(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        assert list(file_notices.known_line_numbers()) == []

        file_notices = file_notices.set_lines(
            {
                2: (ln := file_notices.generate_notices_for_line(2)).set_notices(
                    [ln.generate_notice(msg="n1"), ln.generate_notice(msg="n2")]
                ),
                1: file_notices.generate_notices_for_line(1),
                3: file_notices.generate_notices_for_line(3),
            }
        )
        assert list(file_notices.known_line_numbers()) == [1, 2, 3]

    def test_it_can_clear_notices(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice(msg="n1")
        n2 = ln1.generate_notice(msg="n2")
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice(msg="n3")
        n4 = ln2.generate_notice(msg="n4")
        ln2 = ln2.set_notices([n3, n4], allow_empty=True)

        file_notices = file_notices.set_lines({2: ln1, 3: ln2}).set_name("one", 1)
        assert list(file_notices or []) == [n1, n2, n3, n4]
        assert file_notices.get_line_number("one") == 1

        cleared = file_notices.clear(clear_names=False)
        assert list(file_notices or []) == [n1, n2, n3, n4]
        assert file_notices.get_line_number("one") == 1

        assert cleared is not None
        assert list(cleared) == []
        assert cleared.get_line_number("one") == 1

        cleared_without_names = file_notices.clear(clear_names=True)
        assert list(file_notices or []) == [n1, n2, n3, n4]
        assert file_notices.get_line_number("one") == 1

        assert cleared_without_names is not None
        assert list(cleared_without_names) == []
        assert cleared_without_names.get_line_number("one") is None

    def test_it_can_be_given_notices(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice(msg="n1")
        n2 = ln1.generate_notice(msg="n2")
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice(msg="n3")
        n4 = ln2.generate_notice(msg="n4")
        ln2 = ln2.set_notices([n3, n4], allow_empty=True)

        copy = file_notices.set_lines({2: ln1, 3: ln2})
        assert not file_notices.has_notices
        assert list(file_notices) == []
        assert copy.has_notices
        assert list(copy) == [n1, n2, n3, n4]

    def test_it_can_have_lines_removed(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)

        ln1 = file_notices.generate_notices_for_line(2)
        n1 = ln1.generate_notice(msg="n1")
        n2 = ln1.generate_notice(msg="n2")
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice(msg="n3")
        n4 = ln2.generate_notice(msg="n4")
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
        n1 = ln1.generate_notice(msg="n1")
        n2 = ln1.generate_notice(msg="n2")
        ln1 = ln1.set_notices([n1, n2], allow_empty=True)

        ln2 = file_notices.generate_notices_for_line(3)
        n3 = ln2.generate_notice(msg="n3")
        n4 = ln2.generate_notice(msg="n4")
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
        na1 = ln1.generate_notice(msg="na1")
        nb1 = ln1.generate_notice(msg="nb1")

        ln2 = file_notices.generate_notices_for_line(2)
        na2 = ln2.generate_notice(msg="na2")
        nb2 = ln2.generate_notice(msg="nb2")
        na3 = ln2.generate_notice(msg="na3")
        nb3 = ln2.generate_notice(msg="nb3")

        ln3 = file_notices.generate_notices_for_line(3)
        na4 = ln3.generate_notice(msg="na4")
        nb4 = ln3.generate_notice(msg="nb4")
        na5 = ln3.generate_notice(msg="na5")
        nb5 = ln3.generate_notice(msg="nb5")

        ln4 = file_notices.generate_notices_for_line(4)
        na6 = ln4.generate_notice(msg="na6")
        nb6 = ln4.generate_notice(msg="nb6")

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


class TestProgramNotices:
    def test_it_knows_what_notices_it_has(self, tmp_path: pathlib.Path) -> None:
        program_notices = notices.ProgramNotices()

        fn1 = program_notices.generate_notices_for_location(tmp_path / "one")
        f1l1 = fn1.generate_notices_for_line(1)
        n1 = f1l1.generate_notice(msg="n1")
        n2 = f1l1.generate_notice(msg="n2")
        fn1 = fn1.set_lines({1: f1l1.set_notices([n1, n2])})

        fn2 = program_notices.generate_notices_for_location(tmp_path / "two")
        f2l1 = fn2.generate_notices_for_line(1)
        n3 = f2l1.generate_notice(msg="n3")
        n4 = f2l1.generate_notice(msg="n4")
        f2l5 = fn2.generate_notices_for_line(5)
        n5 = f2l5.generate_notice(msg="n5")
        n6 = f2l5.generate_notice(msg="n6")
        fn2 = fn2.set_lines({1: f2l1.set_notices([n3, n4]), 5: f2l5.set_notices([n5, n6])})

        assert not program_notices.has_notices
        assert list(program_notices) == []
        assert program_notices.notices_at_location(tmp_path / "one") is None

        copy = program_notices.set_files({fn1.location: fn1, fn2.location: fn2})
        assert not program_notices.has_notices
        assert list(program_notices) == []
        assert copy.has_notices
        assert list(copy) == [n1, n2, n3, n4, n5, n6]
        assert copy.notices_at_location(tmp_path / "one") == fn1
        assert copy.notices_at_location(tmp_path / "two") == fn2
        assert copy.notices_at_location(tmp_path / "three") is None

        copy = copy.set_files({fn1.location: fn1, fn2.location: None})
        assert copy.has_notices
        assert list(copy) == [n1, n2]
        assert copy.notices_at_location(tmp_path / "one") == fn1
        assert copy.notices_at_location(tmp_path / "two") is None

        fn3 = program_notices.generate_notices_for_location(tmp_path / "four")
        f3l1 = fn3.generate_notices_for_line(1)
        n7 = f3l1.generate_notice(msg="n7")
        fn3 = fn3.set_lines({1: f3l1.set_notices([n7])})

        copy = copy.set_files({fn3.location: fn3})
        assert copy.has_notices
        assert list(copy) == [n7, n1, n2]
        assert copy.notices_at_location(tmp_path / "one") == fn1
        assert copy.notices_at_location(tmp_path / "two") is None
        assert copy.notices_at_location(tmp_path / "four") == fn3

    def test_it_can_make_a_diff_between_two_program_notices(self, tmp_path: pathlib.Path) -> None:
        program_notices = notices.ProgramNotices()

        fn1 = program_notices.generate_notices_for_location(tmp_path / "a" / "one")
        f1l1 = fn1.generate_notices_for_line(1)
        na1 = f1l1.generate_notice(msg="na1")
        # nb1 = f1l1.generate_notice(msg="nb1")
        na2 = f1l1.generate_notice(msg="na2")
        # nb2 = f1l1.generate_notice(msg="nb2")

        fn2 = program_notices.generate_notices_for_location(tmp_path / "b" / "two")
        f2l1 = fn2.generate_notices_for_line(1)
        na3 = f2l1.generate_notice(msg="na3")
        # nb3 = f2l1.generate_notice(msg="nb3")
        na4 = f2l1.generate_notice(msg="na4")
        # nb4 = f2l1.generate_notice(msg="nb4")
        f2l3 = fn2.generate_notices_for_line(3)
        na5 = f2l3.generate_notice(msg="na5")
        nb5 = f2l3.generate_notice(msg="nb5")
        f2l5 = fn2.generate_notices_for_line(5)
        # na6 = f2l5.generate_notice(msg="na6")
        nb6 = f2l5.generate_notice(msg="nb6")
        # na7 = f2l5.generate_notice(msg="na7")
        nb7 = f2l5.generate_notice(msg="nb7")

        fn3 = program_notices.generate_notices_for_location(tmp_path / "c")
        f3l1 = fn3.generate_notices_for_line(1)
        # na8 = f3l1.generate_notice(msg="na8")
        nb8 = f3l1.generate_notice(msg="nb8")

        fn4 = program_notices.generate_notices_for_location(tmp_path / "d")
        f4l1 = fn4.generate_notices_for_line(1)
        na9 = f4l1.generate_notice(msg="na9")
        # nb9 = f4l1.generate_notice(msg="nb9")
        # na10 = f4l1.generate_notice(msg="na10")
        nb10 = f4l1.generate_notice(msg="nb10")
        f4l8 = fn4.generate_notices_for_line(8)
        na11 = f4l8.generate_notice(msg="na11")
        # nb11 = f4l8.generate_notice(msg="nb11")

        fn5 = program_notices.generate_notices_for_location(
            pathlib.Path("/outside/of/the/tmp/dir")
        )
        f5l6 = fn5.generate_notices_for_line(6)
        na12 = f5l6.generate_notice(msg="na12")
        nb12 = f5l6.generate_notice(msg="nb12")
        f5l9 = fn5.generate_notices_for_line(9)
        # na13 = f5l9.generate_notice(msg="na13")
        nb13 = f5l9.generate_notice(msg="nb13")

        left = program_notices.set_files(
            {
                fn1.location: fn1.set_lines({1: f1l1.set_notices([na1, na2])}),
                fn2.location: fn2.set_lines(
                    {1: f2l1.set_notices([na3, na4]), 3: f2l5.set_notices([na5])}
                ),
                fn4.location: fn4.set_lines(
                    {1: f4l1.set_notices([na9]), 8: f4l8.set_notices([na11])}
                ),
                fn5.location: fn5.set_lines({6: f5l6.set_notices([na12])}),
            }
        )

        right = program_notices.set_files(
            {
                fn2.location: fn2.set_lines(
                    {3: f2l3.set_notices([nb5]), 5: f2l5.set_notices([nb6, nb7])}
                ),
                fn3.location: fn3.set_lines({1: f3l1.set_notices([nb8])}),
                fn4.location: fn4.set_lines({1: f4l1.set_notices([nb10])}),
                fn5.location: fn5.set_lines(
                    {6: f5l6.set_notices([nb12]), 9: f5l9.set_notices([nb13])}
                ),
            }
        )

        diff = left.diff(tmp_path, right)

        expected = notices.DiffNotices(
            by_file={
                "a/one": notices.DiffFileNotices(by_line_number={1: ([na1, na2], [])}),
                "b/two": notices.DiffFileNotices(
                    by_line_number={1: ([na3, na4], []), 3: ([na5], [nb5]), 5: ([], [nb6, nb7])}
                ),
                "c": notices.DiffFileNotices(by_line_number={1: ([], [nb8])}),
                "d": notices.DiffFileNotices(by_line_number={1: ([na9], [nb10]), 8: ([na11], [])}),
                "/outside/of/the/tmp/dir": notices.DiffFileNotices(
                    by_line_number={6: ([na12], [nb12]), 9: ([], [nb13])}
                ),
            }
        )

        assert sorted([l for l, _ in diff]) == sorted(expected.by_file)
        for location, file_diff in sorted(diff):
            assert sorted([i for i, _, _ in file_diff]) == sorted(
                [i for i, _, _ in expected.by_file[location]]
            )
            assert sorted(file_diff) == sorted(expected.by_file[location])

        assert diff == expected

    def test_it_can_get_known_locations(self, tmp_path: pathlib.Path) -> None:
        program_notices = notices.ProgramNotices()

        fn1 = program_notices.generate_notices_for_location(tmp_path / "a" / "one")
        f1l1 = fn1.generate_notices_for_line(1)
        program_notices = program_notices.set_files(
            {fn1.location: fn1.set_lines({f1l1.line_number: f1l1})}
        )
        assert list(program_notices.known_locations()) == [fn1.location]

        fn2 = program_notices.generate_notices_for_location(tmp_path / "b" / "two")
        f2l1 = fn2.generate_notices_for_line(1)
        na3 = f2l1.generate_notice(msg="na3")
        f2l3 = fn2.generate_notices_for_line(3)
        na5 = f2l3.generate_notice(msg="na5")
        program_notices = program_notices.set_files(
            {
                fn2.location: fn2.set_lines(
                    {
                        f2l1.line_number: f2l1.set_notices([na3]),
                        f2l3.line_number: f2l3.set_notices([na5]),
                    }
                ),
            }
        )
        assert list(program_notices.known_locations()) == [fn1.location, fn2.location]


class TestAddRevealedTypes:
    def test_it_can_append_reveal_notices(self, file_notices: protocols.FileNotices) -> None:
        fn5 = file_notices.generate_notices_for_line(5)
        n1 = fn5.generate_notice(msg="n1")

        file_notices = file_notices.set_name("one", 5).set_lines({5: fn5.set_notices([n1])})

        changer = notices.AddRevealedTypes(name="one", revealed=["one", "two"], replace=False)

        changed = changer(file_notices)
        assert list(file_notices) == [n1]
        assert list(changed) == [
            n1,
            matchers.MatchNote(
                location=file_notices.location,
                line_number=5,
                msg=f"{notices.ProgramNotice.reveal_msg('one')}\n{notices.ProgramNotice.reveal_msg('two')}",
            ),
        ]

    def test_it_can_replace_existing_reveal_notices(
        self, file_notices: protocols.FileNotices
    ) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("three"))
        n4 = fn5.generate_notice(msg="a note")
        n5 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("four"))
        n6 = fn5.generate_notice(msg="an error", severity=notices.ErrorSeverity("arg-type"))
        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6]),
            }
        )

        changer = notices.AddRevealedTypes(
            name="the_one_line", revealed=["five", "six"], replace=True
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n4,
            n6,
            matchers.MatchNote(
                location=file_notices.location,
                line_number=5,
                msg=f"{notices.ProgramNotice.reveal_msg('five')}\n{notices.ProgramNotice.reveal_msg('six')}",
            ),
        ]

    def test_it_can_replace_when_none_existing(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {fn1.line_number: fn1.set_notices([n1, n2])}
        )

        changer = notices.AddRevealedTypes(
            name="the_one_line", revealed=["five", "six"], replace=True
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == []

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            matchers.MatchNote(
                location=file_notices.location,
                line_number=5,
                msg=f"{notices.ProgramNotice.reveal_msg('five')}\n{notices.ProgramNotice.reveal_msg('six')}",
            ),
        ]

    def test_it_complains_if_name_not_registered(
        self, file_notices: protocols.FileNotices
    ) -> None:
        changer = notices.AddRevealedTypes(
            name="the_one_line", revealed=["five", "six"], replace=True
        )

        with pytest.raises(notice_changers.MissingNotices) as e:
            changer(file_notices)

        assert e.value.location == file_notices.location
        assert e.value.name == "the_one_line"


class TestAddErrors:
    def test_it_can_append_error_notices(self, file_notices: protocols.FileNotices) -> None:
        fn5 = file_notices.generate_notices_for_line(5)
        n1 = fn5.generate_notice(msg="n1")

        file_notices = file_notices.set_name("one", 5).set_lines({5: fn5.set_notices([n1])})

        changer = notices.AddErrors(
            name="one",
            errors=[("misc", "one"), ("misc", "two"), ("arg-type", "three")],
            replace=False,
        )

        changed = changer(file_notices)
        assert list(file_notices) == [n1]
        assert list(changed) == [
            n1,
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("misc"),
                msg="one",
            ),
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("misc"),
                msg="two",
            ),
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("arg-type"),
                msg="three",
            ),
        ]

    def test_it_can_replace_existing_errors(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("three"))
        n4 = fn5.generate_notice(msg="an error", severity=notices.ErrorSeverity("var-annotated"))
        n5 = fn5.generate_notice(msg="a note")
        n6 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("four"))
        n7 = fn5.generate_notice(msg="another error", severity=notices.ErrorSeverity("arg-type"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6, n7]),
            }
        )

        changer = notices.AddErrors(
            name="the_one_line",
            errors=[("typeddict-item", "five"), ("assignment", "six")],
            replace=True,
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6, n7]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n3,
            n5,
            n6,
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("typeddict-item"),
                msg="five",
            ),
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("assignment"),
                msg="six",
            ),
        ]

    def test_it_can_replace_when_none_existing(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {fn1.line_number: fn1.set_notices([n1, n2])}
        )

        changer = notices.AddErrors(
            name="the_one_line", errors=[("arg-type", "five"), ("misc", "six")], replace=True
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == []

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("arg-type"),
                msg="five",
            ),
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("misc"),
                msg="six",
            ),
        ]

    def test_it_complains_if_name_not_registered(
        self, file_notices: protocols.FileNotices
    ) -> None:
        changer = notices.AddErrors(name="the_one_line", errors=[("misc", "five")], replace=True)

        with pytest.raises(notice_changers.MissingNotices) as e:
            changer(file_notices)

        assert e.value.location == file_notices.location
        assert e.value.name == "the_one_line"


class TestAddNotes:
    def test_it_can_append_notes(self, file_notices: protocols.FileNotices) -> None:
        fn5 = file_notices.generate_notices_for_line(5)
        n1 = fn5.generate_notice(msg="n1")

        file_notices = file_notices.set_name("one", 5).set_lines({5: fn5.set_notices([n1])})

        changer = notices.AddNotes(name="one", notes=["one", "two"], replace=False)

        changed = changer(file_notices)
        assert list(file_notices) == [n1]
        assert list(changed) == [
            n1,
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="one\ntwo"),
        ]

    def test_it_can_replace_existing_notes(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("three"))
        n4 = fn5.generate_notice(msg="a note")
        n5 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("four"))
        n6 = fn5.generate_notice(msg="an error", severity=notices.ErrorSeverity("arg-type"))
        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6]),
            }
        )

        changer = notices.AddNotes(
            name="the_one_line", notes=["five", "six"], keep_reveals=False, replace=True
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n6,
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="five\nsix"),
        ]

    def test_it_can_replace_existing_non_reveal_notes(
        self, file_notices: protocols.FileNotices
    ) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("three"))
        n4 = fn5.generate_notice(msg="a note")
        n5 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("four"))
        n6 = fn5.generate_notice(msg="an error", severity=notices.ErrorSeverity("arg-type"))
        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6]),
            }
        )

        changer = notices.AddNotes(
            name="the_one_line", notes=["five", "six"], keep_reveals=True, replace=True
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n3,
            n5,
            n6,
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="five\nsix"),
        ]

    def test_it_defaults_to_not_replacing_reveals(
        self, file_notices: protocols.FileNotices
    ) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("three"))
        n4 = fn5.generate_notice(msg="a note")
        n5 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("four"))
        n6 = fn5.generate_notice(msg="an error", severity=notices.ErrorSeverity("arg-type"))
        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6]),
            }
        )

        changer = notices.AddNotes(name="the_one_line", notes=["five", "six"], replace=True)

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n3,
            n5,
            n6,
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="five\nsix"),
        ]

    def test_it_can_replace_when_none_existing(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {fn1.line_number: fn1.set_notices([n1, n2])}
        )

        changer = notices.AddNotes(name="the_one_line", notes=["five", "six"], replace=True)

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == []

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="five\nsix"),
        ]

    def test_it_complains_if_name_not_registered(
        self, file_notices: protocols.FileNotices
    ) -> None:
        changer = notices.AddNotes(name="the_one_line", notes=["five", "six"], replace=True)

        with pytest.raises(notice_changers.MissingNotices) as e:
            changer(file_notices)

        assert e.value.location == file_notices.location
        assert e.value.name == "the_one_line"


class TestRemoveFromRevealedType:
    def test_it_can_remove_from_existing_reveal_notices(
        self, file_notices: protocols.FileNotices
    ) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("l1_a_replaceable_message"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("l1_two"))

        fn5 = file_notices.generate_notices_for_line(5)
        n3 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("l5_a_replaceable_message"))
        n4 = fn5.generate_notice(msg="l5_b_replaceable_message")
        n5 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("l5_four"))
        n6 = fn5.generate_notice(
            msg="l5_c_replaceable_message", severity=notices.ErrorSeverity("arg-type")
        )
        n7 = fn5.generate_notice(msg="replaceable", severity=notices.ErrorSeverity("assignment"))
        n8 = fn5.generate_notice(msg=notices.ProgramNotice.reveal_msg("l5replaceable_tree"))
        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {
                fn1.line_number: fn1.set_notices([n1, n2]),
                fn5.line_number: fn5.set_notices([n3, n4, n5, n6, n7, n8]),
            }
        )

        changer = notices.RemoveFromRevealedType(name="the_one_line", remove="replaceable")

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == [n3, n4, n5, n6, n7, n8]

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == [
            n3.clone(msg=notices.ProgramNotice.reveal_msg("l5_a__message")),
            n4,
            n5,
            n6,
            n7,
            n8.clone(msg=notices.ProgramNotice.reveal_msg("l5_tree")),
        ]

    def test_it_complains_if_none_matching(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {fn1.line_number: fn1.set_notices([n1, n2])}
        )

        changer = notices.RemoveFromRevealedType(name="the_one_line", remove="replaceme")

        with pytest.raises(notice_changers.MissingNotices) as e:
            changer(file_notices)

        assert e.value.location == file_notices.location
        assert e.value.name == "the_one_line"
        assert e.value.line_number == 5

    def test_it_can_ignore_none_matching(self, file_notices: protocols.FileNotices) -> None:
        fn1 = file_notices.generate_notices_for_line(1)
        n1 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("one"))
        n2 = fn1.generate_notice(msg=notices.ProgramNotice.reveal_msg("two"))

        file_notices = file_notices.set_name("the_one_line", 5).set_lines(
            {fn1.line_number: fn1.set_notices([n1, n2])}
        )

        changer = notices.RemoveFromRevealedType(
            name="the_one_line", remove="replaceme", must_exist=False
        )

        changed = changer(file_notices)

        assert list(file_notices.notices_at_line(1) or []) == [n1, n2]
        assert list(file_notices.notices_at_line(5) or []) == []

        assert list(changed.notices_at_line(1) or []) == [n1, n2]
        assert list(changed.notices_at_line(5) or []) == []

    def test_it_complains_if_name_not_registered(
        self, file_notices: protocols.FileNotices
    ) -> None:
        changer = notices.RemoveFromRevealedType(name="the_one_line", remove="deleteme")

        with pytest.raises(notice_changers.MissingNotices) as e:
            changer(file_notices)

        assert e.value.location == file_notices.location
        assert e.value.name == "the_one_line"
