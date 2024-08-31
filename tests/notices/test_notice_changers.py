import pathlib

import pytest
from pytest_typing_runner_test_driver import matchers

from pytest_typing_runner import notice_changers, notices, protocols


@pytest.fixture
def file_notices(tmp_path: pathlib.Path) -> protocols.FileNotices:
    pm = notices.ProgramNotices()
    return pm.generate_notices_for_location(tmp_path)


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
            errors=[
                ("misc", "one"),
                ("misc", "two"),
                ("arg-type", "three"),
                ("assignment", notices.RegexMsg.create(pattern="stuff .+")),
            ],
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
            matchers.MatchNotice(
                location=file_notices.location,
                line_number=5,
                severity=notices.ErrorSeverity("assignment"),
                msg="stuff and things",
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

        changer = notices.AddNotes(
            name="one",
            notes=["one", "two", notices.GlobMsg.create(pattern="one * two")],
            replace=False,
        )

        changed = changer(file_notices)
        assert list(file_notices) == [n1]
        assert list(changed) == [
            n1,
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="one"),
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="two"),
            matchers.MatchNote(location=file_notices.location, line_number=5, msg="one t two"),
        ]

    def test_it_collapses_notes_when_all_strings(
        self, file_notices: protocols.FileNotices
    ) -> None:
        fn5 = file_notices.generate_notices_for_line(5)
        n1 = fn5.generate_notice(msg="n1")

        file_notices = file_notices.set_name("one", 5).set_lines({5: fn5.set_notices([n1])})

        changer = notices.AddNotes(
            name="one",
            notes=["one", "two"],
            replace=False,
        )

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
