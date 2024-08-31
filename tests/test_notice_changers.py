import pathlib
from collections.abc import Sequence

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notice_changers, notices, protocols


class TestMissingNotices:
    def test_it_has_a_string_transformation(self, tmp_path: pathlib.Path) -> None:
        exc = notice_changers.MissingNotices(location=tmp_path)
        assert str(exc) == f"Failed to find registered notices for {tmp_path}"

        exc = notice_changers.MissingNotices(location=tmp_path, name="thing")
        assert str(exc) == f"Failed to find registered notices for {tmp_path} (thing)"

        exc = notice_changers.MissingNotices(location=tmp_path, line_number=20)
        assert str(exc) == f"Failed to find registered notices for {tmp_path}:20"

        exc = notice_changers.MissingNotices(location=tmp_path, line_number=30, name="stuff")
        assert str(exc) == f"Failed to find registered notices for {tmp_path}:30 (stuff)"


@pytest.fixture
def file_notices(tmp_path: pathlib.Path) -> protocols.FileNotices:
    pm = notices.ProgramNotices()
    return pm.generate_notices_for_location(tmp_path)


@pytest.fixture
def line_notices(file_notices: protocols.FileNotices) -> protocols.LineNotices:
    return file_notices.generate_notices_for_line(10)


@pytest.fixture
def notice(line_notices: protocols.LineNotices) -> protocols.ProgramNotice:
    return line_notices.generate_notice(severity=notices.NoteSeverity(), msg="stuff")


class TestFirstMatchOnly:
    def test_it_only_uses_change_the_first_time(self, notice: protocols.ProgramNotice) -> None:
        def change(n: protocols.ProgramNotice, /) -> protocols.ProgramNotice:
            return n.clone(msg="hi")

        n1 = notice.clone(msg="one")
        n2 = notice.clone(msg="two")
        n3 = notice.clone(msg="three")

        first_match = notice_changers.FirstMatchOnly(change=change)

        changed = first_match(n1)
        assert changed is not None
        assert changed is not n1
        assert n1.msg == "one"
        assert changed.msg == "hi"

        assert first_match(n2) is n2
        assert first_match(n3) is n3

        # And even the one it did change no longer gets changed again
        assert first_match(n1) is n1


class TestAppendToLine:
    def test_it_always_allows_empty(self, line_notices: protocols.LineNotices) -> None:
        assert list(line_notices) == []

        def make_notices(ln: protocols.LineNotices, /) -> Sequence[protocols.ProgramNotice | None]:
            return []

        changed = notice_changers.AppendToLine(notices_maker=make_notices)(line_notices)
        assert changed is not line_notices
        assert list(line_notices) == []

    def test_it_can_create_a_clone_with_no_new_notices(
        self, line_notices: protocols.LineNotices
    ) -> None:
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")

        line_notices = line_notices.set_notices([n1, n2], allow_empty=True)
        assert list(line_notices) == [n1, n2]

        def make_notices(ln: protocols.LineNotices, /) -> Sequence[protocols.ProgramNotice | None]:
            return []

        changed = notice_changers.AppendToLine(notices_maker=make_notices)(line_notices)
        assert list(changed) == [n1, n2]
        assert list(line_notices) == [n1, n2]

        def make_notices2(
            ln: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [None, None]

        changed = notice_changers.AppendToLine(notices_maker=make_notices2)(line_notices)
        assert list(changed) == [n1, n2]
        assert list(line_notices) == [n1, n2]

    def test_it_can_append_to_the_notices(self, line_notices: protocols.LineNotices) -> None:
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
        n3 = line_notices.generate_notice(msg="n3")
        n4 = line_notices.generate_notice(msg="n4")
        n5 = line_notices.generate_notice(msg="n5")

        line_notices = line_notices.set_notices([n1, n2], allow_empty=True)
        assert list(line_notices) == [n1, n2]

        def make_notices(ln: protocols.LineNotices, /) -> Sequence[protocols.ProgramNotice | None]:
            return [n3, None, n4]

        changed = notice_changers.AppendToLine(notices_maker=make_notices)(line_notices)
        assert list(changed) == [n1, n2, n3, n4]
        assert list(line_notices) == [n1, n2]

        def make_notices2(
            ln: protocols.LineNotices, /
        ) -> Sequence[protocols.ProgramNotice | None]:
            return [n5]

        changed = notice_changers.AppendToLine(notices_maker=make_notices2)(changed)
        assert list(changed) == [n1, n2, n3, n4, n5]
        assert list(line_notices) == [n1, n2]


class TestModifyLatestMatch:
    def test_it_only_changes_the_notice_from_the_end_that_matches(
        self, line_notices: protocols.LineNotices
    ) -> None:
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
        n3 = line_notices.generate_notice(msg="n3")
        s1 = line_notices.generate_notice(msg="s1")
        s2 = line_notices.generate_notice(msg="s2")
        d1 = line_notices.generate_notice(msg="d1")

        assert [
            n.msg
            for n in notice_changers.ModifyLatestMatch(
                change=lambda n: n.clone(msg="changed!"),
                matcher=lambda n: n.msg.raw.startswith("s"),
            )(line_notices.set_notices([n1, n2, s1, d1, s2, n3], allow_empty=True))
            or []
        ] == ["n1", "n2", "s1", "d1", "changed!", "n3"]

        assert [
            n.msg
            for n in notice_changers.ModifyLatestMatch(
                change=lambda n: n.clone(msg="changed!"),
                matcher=lambda n: n.msg.raw.startswith("s"),
            )(line_notices.set_notices([n1, n2, s1, d1, n3], allow_empty=True))
            or []
        ] == ["n1", "n2", "changed!", "d1", "n3"]

    def test_it_can_add_to_the_end_if_does_not_exist(
        self, line_notices: protocols.LineNotices
    ) -> None:
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
        n3 = line_notices.generate_notice(msg="n3")

        assert [
            n.msg
            for n in notice_changers.ModifyLatestMatch(
                change=lambda n: n.clone(msg="changed!"),
                matcher=lambda n: n.msg.raw.startswith("s"),
            )(line_notices.set_notices([n1, n2, n3], allow_empty=True))
            or []
        ] == ["n1", "n2", "n3", "changed!"]

    def test_it_can_be_told_to_complain_if_does_not_exist(
        self, line_notices: protocols.LineNotices
    ) -> None:
        n1 = line_notices.generate_notice(msg="n1")
        n2 = line_notices.generate_notice(msg="n2")
        n3 = line_notices.generate_notice(msg="n3")

        with pytest.raises(notice_changers.MissingNotices) as e:
            assert notice_changers.ModifyLatestMatch(
                must_exist=True,
                change=lambda n: n.clone(msg="changed!"),
                matcher=lambda n: n.msg.raw.startswith("s"),
            )(line_notices.set_notices([n1, n2, n3], allow_empty=True))

        assert e.value.location == line_notices.location
        assert e.value.line_number == line_notices.line_number

    def test_it_can_result_in_empty_notices(self, line_notices: protocols.LineNotices) -> None:
        n1 = line_notices.generate_notice(msg="n1")

        assert (
            notice_changers.ModifyLatestMatch(
                change=lambda n: None,
                matcher=lambda n: n.msg.raw.startswith("n"),
            )(line_notices.set_notices([n1], allow_empty=True))
            is None
        )

        changed = notice_changers.ModifyLatestMatch(
            allow_empty=True,
            change=lambda n: None,
            matcher=lambda n: n.msg.raw.startswith("n"),
        )(line_notices.set_notices([n1], allow_empty=True))
        assert changed is not None
        assert list(changed) == []

        changed = notice_changers.ModifyLatestMatch(
            allow_empty=True,
            change=lambda n: None,
            matcher=lambda n: n.msg.raw.startswith("n"),
        )(line_notices.set_notices([], allow_empty=True))
        assert changed is not None
        assert list(changed) == []

        assert (
            notice_changers.ModifyLatestMatch(
                change=lambda n: None,
                matcher=lambda n: n.msg.raw.startswith("n"),
            )(line_notices.set_notices([], allow_empty=True))
            is None
        )


class TestModifyLine:
    def test_it_can_complain_if_name_is_not_registered(
        self, file_notices: protocols.FileNotices
    ) -> None:
        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyLine(
                name_must_exist=True, name_or_line="one", change=lambda ln: None
            )(file_notices)

        assert e.value.location == file_notices.location

    def test_it_can_complain_if_name_is_registered_but_no_notices_at_line(
        self, file_notices: protocols.FileNotices
    ) -> None:
        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyLine(
                name_must_exist=True,
                line_must_exist=True,
                name_or_line="one",
                change=lambda ln: None,
            )(file_notices.set_name("one", 1))

        assert e.value.location == file_notices.location

    def test_it_can_complain_if_no_notices_at_line(
        self, file_notices: protocols.FileNotices
    ) -> None:
        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyLine(
                name_must_exist=True,
                line_must_exist=True,
                name_or_line=1,
                change=lambda ln: None,
            )(file_notices)

        assert e.value.location == file_notices.location

        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyLine(
                name_must_exist=True,
                line_must_exist=True,
                name_or_line=1,
                change=lambda ln: None,
            )(file_notices.set_name("one", 1))

        assert e.value.location == file_notices.location

        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyLine(
                name_must_exist=False,
                line_must_exist=True,
                name_or_line=1,
                change=lambda ln: None,
            )(file_notices.set_name("one", 1))

        assert e.value.location == file_notices.location

    def test_it_keeps_named_lines_when_empty_after(
        self, file_notices: protocols.FileNotices
    ) -> None:
        l1 = file_notices.generate_notices_for_line(1)
        n1 = l1.generate_notice(msg="n1")
        file_notices = file_notices.set_lines({1: l1.set_notices([n1])}).set_name("one", 1)
        assert list(file_notices) == [n1]
        assert file_notices.get_line_number("one") == 1

        file_notices = notice_changers.ModifyLine(name_or_line=1, change=lambda ln: None)(
            file_notices
        )
        assert list(file_notices) == []
        assert file_notices.get_line_number("one") == 1

    def test_it_can_add_line_if_not_already_exists(
        self, file_notices: protocols.FileNotices
    ) -> None:
        l1 = file_notices.generate_notices_for_line(1)
        n1 = l1.generate_notice(msg="n1")
        n2 = l1.generate_notice(msg="n2")
        assert list(file_notices) == []

        file_notices = notice_changers.ModifyLine(
            name_or_line=1, line_must_exist=False, change=lambda ln: ln.set_notices([n1])
        )(file_notices)
        assert list(file_notices) == [n1]
        assert list(file_notices.notices_at_line(1) or []) == [n1]

        file_notices = notice_changers.ModifyLine(
            name_or_line="one",
            name_must_exist=False,
            line_must_exist=False,
            change=lambda ln: ln.set_notices([n2]),
        )(file_notices.set_name("one", 5))
        assert list(file_notices) == [n1, n2]
        assert list(file_notices.notices_at_line(1) or []) == [n1]
        assert list(file_notices.notices_at_line(5) or []) == [n2]


class TestModifyFile:
    def test_it_complains_if_location_does_not_exist(self, tmp_path: pathlib.Path) -> None:
        program_notices = notices.ProgramNotices()

        with pytest.raises(notice_changers.MissingNotices) as e:
            notice_changers.ModifyFile(
                location=tmp_path,
                must_exist=True,
                change=lambda fn: fn,
            )(program_notices)

        assert e.value.location == tmp_path

    def test_it_can_create_new_file_notices(self, tmp_path: pathlib.Path) -> None:
        program_notices: protocols.ProgramNotices = notices.ProgramNotices()

        fn1 = program_notices.generate_notices_for_location(tmp_path)
        ln1 = fn1.generate_notices_for_line(1)
        n1 = ln1.generate_notice(msg="n1")

        assert list(program_notices) == []

        program_notices = notice_changers.ModifyFile(
            location=tmp_path,
            must_exist=False,
            change=lambda fn: fn.set_lines({1: ln1.set_notices([n1])}),
        )(program_notices)

        assert list(program_notices) == [n1]

        ff1 = program_notices.notices_at_location(tmp_path)
        assert ff1 is not None
        assert list(ff1) == [n1]
        fl1 = ff1.notices_at_line(1)
        assert fl1 is not None
        assert list(fl1) == [n1]

    def test_it_can_change_existing_file_notices(self, tmp_path: pathlib.Path) -> None:
        program_notices: protocols.ProgramNotices = notices.ProgramNotices()

        fn1 = program_notices.generate_notices_for_location(tmp_path)
        ln1 = fn1.generate_notices_for_line(1)
        n1 = ln1.generate_notice(msg="n1")
        ln2 = fn1.generate_notices_for_line(2)
        n2 = ln2.generate_notice(msg="n2")

        program_notices = program_notices.set_files(
            {tmp_path: fn1.set_lines({1: ln1.set_notices([n1])})}
        )
        assert list(program_notices) == [n1]

        program_notices = notice_changers.ModifyFile(
            location=tmp_path,
            change=lambda fn: fn.set_lines({2: ln2.set_notices([n2])}),
        )(program_notices)
        assert list(program_notices) == [n1, n2]

        ff1 = program_notices.notices_at_location(tmp_path)
        assert ff1 is not None
        assert list(ff1.notices_at_line(1) or []) == [n1]
        assert list(ff1.notices_at_line(2) or []) == [n2]


class TestBulkAdd:
    def test_it_can_bulk_add(self, tmp_path: pathlib.Path) -> None:
        def names(notices: protocols.ProgramNotices) -> dict[tuple[str, int], str]:
            result: dict[tuple[str, int], str] = {}
            for location in notices.known_locations():
                path = str(location.relative_to(tmp_path))
                file_notices = notices.notices_at_location(location)
                assert file_notices is not None
                for name, line_number in file_notices.known_names.items():
                    result[(path, line_number)] = name
            return result

        program_notices: protocols.ProgramNotices = notices.ProgramNotices()
        assert list(program_notices) == []
        assert names(program_notices) == {}

        program_notices = notice_changers.BulkAdd(root_dir=tmp_path, add={})(program_notices)
        assert list(program_notices) == []
        assert names(program_notices) == {}

        program_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={
                "one": {1: "hello"},
                "two/three": {20: ["there"]},
            },
        )(program_notices)
        assert list(program_notices) == [
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="hello"),
            matchers.MatchNote(location=tmp_path / "two/three", line_number=20, msg="there"),
        ]
        assert names(program_notices) == {}

        program_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={
                "one": {1: ["there"], 2: [(notices.ErrorSeverity("arg-type"), "e1"), "things"]},
                "two/three": {(20, "blah"): []},
                "four": {20: [(notices.ErrorSeverity("assignment"), "e2")]},
            },
        )(program_notices)
        assert sorted(program_notices) == [
            matchers.MatchNotice(
                location=tmp_path / "four",
                line_number=20,
                severity=notices.ErrorSeverity("assignment"),
                msg="e2",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="hello"),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="there"),
            matchers.MatchNotice(
                location=tmp_path / "one",
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="e1",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=2, msg="things"),
            matchers.MatchNote(location=tmp_path / "two/three", line_number=20, msg="there"),
        ]
        assert names(program_notices) == {("two/three", 20): "blah"}

        program_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={
                "one": {(2, "other"): ["things2"]},
                "two/three": {20: []},
                "four": {20: [(notices.ErrorSeverity("var-annotated"), "e3")]},
                "five": {(1, "tree"): []},
            },
        )(program_notices)
        assert sorted(program_notices) == [
            matchers.MatchNotice(
                location=tmp_path / "four",
                line_number=20,
                severity=notices.ErrorSeverity("assignment"),
                msg="e2",
            ),
            matchers.MatchNotice(
                location=tmp_path / "four",
                line_number=20,
                severity=notices.ErrorSeverity("var-annotated"),
                msg="e3",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="hello"),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="there"),
            matchers.MatchNotice(
                location=tmp_path / "one",
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="e1",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=2, msg="things"),
            matchers.MatchNote(location=tmp_path / "one", line_number=2, msg="things2"),
            matchers.MatchNote(location=tmp_path / "two/three", line_number=20, msg="there"),
        ]
        assert names(program_notices) == {
            ("one", 2): "other",
            ("two/three", 20): "blah",
            ("five", 1): "tree",
        }

        program_notices = notice_changers.BulkAdd(
            root_dir=tmp_path,
            add={
                "with_regex": {
                    50: [notices.RegexMsg.create(pattern="a{3}")],
                }
            },
        )(program_notices)
        assert sorted(program_notices) == [
            matchers.MatchNotice(
                location=tmp_path / "four",
                line_number=20,
                severity=notices.ErrorSeverity("assignment"),
                msg="e2",
            ),
            matchers.MatchNotice(
                location=tmp_path / "four",
                line_number=20,
                severity=notices.ErrorSeverity("var-annotated"),
                msg="e3",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="hello"),
            matchers.MatchNote(location=tmp_path / "one", line_number=1, msg="there"),
            matchers.MatchNotice(
                location=tmp_path / "one",
                line_number=2,
                severity=notices.ErrorSeverity("arg-type"),
                msg="e1",
            ),
            matchers.MatchNote(location=tmp_path / "one", line_number=2, msg="things"),
            matchers.MatchNote(location=tmp_path / "one", line_number=2, msg="things2"),
            matchers.MatchNote(location=tmp_path / "two/three", line_number=20, msg="there"),
            matchers.MatchNote(location=tmp_path / "with_regex", line_number=50, msg="aaa"),
        ]
        assert names(program_notices) == {
            ("one", 2): "other",
            ("two/three", 20): "blah",
            ("five", 1): "tree",
        }
