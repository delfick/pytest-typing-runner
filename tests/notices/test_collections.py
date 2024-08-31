import pathlib

from pytest_typing_runner import notices, protocols


class TestLineNotices:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        line_notices = notices.LineNotices(location=tmp_path, line_number=2)
        assert line_notices.location == tmp_path
        assert line_notices.line_number == 2
        assert line_notices.msg_maker == notices.PlainMsg.create

        assert not line_notices.has_notices
        assert list(line_notices) == []

        line_notices = notices.LineNotices(
            location=tmp_path, line_number=3, msg_maker=notices.GlobMsg.create
        )
        assert line_notices.msg_maker == notices.GlobMsg.create

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
        assert isinstance(n1.msg, notices.PlainMsg)

        n2 = line_notices.generate_notice(msg="n2", severity=notices.ErrorSeverity("arg-type"))
        assert n2.location == tmp_path
        assert n2.line_number == 2
        assert n2.severity == notices.ErrorSeverity("arg-type")
        assert n2.msg == "n2"
        assert n2.col is None
        assert isinstance(n2.msg, notices.PlainMsg)

        n3 = line_notices.generate_notice(msg="other")
        assert n3.location == tmp_path
        assert n3.line_number == 2
        assert n3.severity == notices.NoteSeverity()
        assert n3.msg == "other"
        assert n3.col is None
        assert isinstance(n3.msg, notices.PlainMsg)

        n4 = line_notices.generate_notice(msg="stuff", msg_maker=notices.RegexMsg.create)
        assert n4.location == tmp_path
        assert n4.line_number == 2
        assert n4.severity == notices.NoteSeverity()
        assert n4.msg == "stuff"
        assert n4.col is None
        assert isinstance(n4.msg, notices.RegexMsg)

        line_notices = notices.LineNotices(
            location=tmp_path, line_number=3, msg_maker=notices.GlobMsg.create
        )
        n5 = line_notices.generate_notice(msg="n5")
        assert n5.location == tmp_path
        assert n5.line_number == 3
        assert n5.severity == notices.NoteSeverity()
        assert n5.msg == "n5"
        assert n5.col is None
        assert isinstance(n5.msg, notices.GlobMsg)

        n6 = line_notices.generate_notice(msg="n6", msg_maker=notices.PlainMsg.create)
        assert n6.location == tmp_path
        assert n6.line_number == 3
        assert n6.severity == notices.NoteSeverity()
        assert n6.msg == "n6"
        assert n6.col is None
        assert isinstance(n6.msg, notices.PlainMsg)


class TestFileNotices:
    def test_it_has_properties(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        assert file_notices.location == tmp_path
        assert file_notices.msg_maker == notices.PlainMsg.create
        assert not file_notices.has_notices
        assert list(file_notices) == []

        file_notices = notices.FileNotices(location=tmp_path, msg_maker=notices.GlobMsg.create)
        assert file_notices.msg_maker == notices.GlobMsg.create

    def test_it_can_get_known_names(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        assert file_notices.known_names == {}
        assert file_notices.set_name("one", 1).set_name("two", 2).known_names == {
            "one": 1,
            "two": 2,
        }

    def test_it_can_generate_line_notices(self, tmp_path: pathlib.Path) -> None:
        file_notices = notices.FileNotices(location=tmp_path)
        line_notices = file_notices.generate_notices_for_line(3)
        assert line_notices.location == tmp_path
        assert line_notices.msg_maker == notices.PlainMsg.create
        assert line_notices.line_number == 3
        assert file_notices.notices_at_line(3) is None

        file_notices = notices.FileNotices(location=tmp_path, msg_maker=notices.GlobMsg.create)
        line_notices = file_notices.generate_notices_for_line(3)
        assert line_notices.location == tmp_path
        assert line_notices.msg_maker == notices.GlobMsg.create
        assert line_notices.line_number == 3
        assert file_notices.notices_at_line(3) is None

        line_notices = file_notices.generate_notices_for_line(3, msg_maker=notices.RegexMsg.create)
        assert line_notices.location == tmp_path
        assert line_notices.msg_maker == notices.RegexMsg.create
        assert line_notices.line_number == 3
        assert file_notices.notices_at_line(3) is None

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

    def test_it_can_generate_file_notices(self, tmp_path: pathlib.Path) -> None:
        program_notices = notices.ProgramNotices()
        file_notices = program_notices.generate_notices_for_location(tmp_path)
        assert file_notices.location == tmp_path
        assert file_notices.msg_maker == notices.PlainMsg.create
        assert program_notices.notices_at_location(tmp_path) is None

        program_notices = notices.ProgramNotices(msg_maker=notices.GlobMsg.create)
        file_notices = program_notices.generate_notices_for_location(tmp_path)
        assert file_notices.location == tmp_path
        assert file_notices.msg_maker == notices.GlobMsg.create
        assert program_notices.notices_at_location(tmp_path) is None

        file_notices = program_notices.generate_notices_for_location(
            tmp_path, msg_maker=notices.RegexMsg.create
        )
        assert file_notices.location == tmp_path
        assert file_notices.msg_maker == notices.RegexMsg.create
        assert program_notices.notices_at_location(tmp_path) is None
