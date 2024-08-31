import pathlib

from pytest_typing_runner import notices, protocols


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
            return notices.ProgramNotice.create(
                location=location,
                line_number=0,
                severity=notices.NoteSeverity(),
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
