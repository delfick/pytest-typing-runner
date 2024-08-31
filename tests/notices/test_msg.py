import re

import pytest

from pytest_typing_runner import notices, protocols


class _BaseNoticeTests:
    def test_it_stores_raw_string(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="hello there")
        assert msg.raw == "hello there"

    def test_it_has_methods_for_dunder_str_and_repr(
        self, msg_maker: protocols.NoticeMsgMaker
    ) -> None:
        raw = "sdfkj aslkdjflkas djf"
        msg = msg_maker(pattern=raw)
        assert str(msg) == str(raw)
        assert repr(msg) == repr(raw)

    def test_it_has_method_for_comparison(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        raw = "sdfkj aslkdjflkas djf"
        msg = msg_maker(pattern=raw)
        assert msg == raw
        assert msg != ""
        assert msg != "hello"

    def test_it_can_be_hashed(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg1 = msg_maker(pattern="one")
        msg2 = msg_maker(pattern="two")

        d: dict[str | protocols.NoticeMsg, int] = {}

        d[msg1] = 2
        d[msg2] = 3

        assert d == {msg1: 2, msg2: 3}
        assert list(d.keys()) == [msg1, msg2]

        d["one"] = 4

        assert d == {msg1: 4, msg2: 3}
        assert list(d.keys()) == ["one", msg2]

    def test_it_can_be_sorted(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg1 = msg_maker(pattern="a")
        msg2 = msg_maker(pattern="b")
        msg3 = msg_maker(pattern="c")
        msg4 = msg_maker(pattern="d")

        assert sorted([msg3, msg2, msg4, msg1]) == [msg1, msg2, msg3, msg4]

    def test_it_can_have_portion_of_raw_replaced(
        self, msg_maker: protocols.NoticeMsgMaker
    ) -> None:
        msg = msg_maker(pattern="hello there")
        msg2 = msg.replace("there", "world")
        assert isinstance(msg2, type(msg))
        assert msg2.raw == "hello world"

    def test_it_can_split_by_each_line(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="hello there")
        split = list(msg.split_lines())
        assert len(split) == 1
        assert split[0] is msg

        msg = msg_maker(pattern="one\ntwo\nthree\n")
        split = list(msg.split_lines())
        assert len(split) == 4
        assert all(isinstance(m, type(msg)) for m in split)
        assert split == ["one", "two", "three", ""]

    def test_it_can_clone(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="two")
        clone = msg.clone(pattern="three")
        assert isinstance(clone, type(msg))
        assert clone.raw == "three"


class TestPlainMsg:
    @pytest.fixture
    def msg_maker(self) -> protocols.NoticeMsgMaker:
        return notices.PlainMsg.create

    class TestBaseFeatures(_BaseNoticeTests):
        pass

    def test_it_has_a_constructor(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert msg_maker == notices.PlainMsg.create
        msg = msg_maker(pattern="hi")
        assert isinstance(msg, notices.PlainMsg)
        assert msg.raw == "hi"

    def test_it_says_its_plain(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert msg_maker(pattern="one").is_plain

    def test_it_matches_with_equality(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="one.*")
        assert msg.match(want="one.*")
        assert not msg.match(want="one")
        assert not msg.match(want="one_")
        assert not msg.match(want="two")


class TestRegexMsg:
    @pytest.fixture
    def msg_maker(self) -> protocols.NoticeMsgMaker:
        return notices.RegexMsg.create

    class TestBaseFeatures(_BaseNoticeTests):
        pass

    def test_it_has_a_constructor(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert msg_maker == notices.RegexMsg.create
        msg = msg_maker(pattern="hi")
        assert isinstance(msg, notices.RegexMsg)
        assert msg.raw == "hi"
        assert msg.regex.pattern == "hi"
        assert msg.regex.match("hi") is not None
        assert msg.regex.match("2") is None

    def test_it_complains_if_pattern_is_invalid_on_construction(
        self, msg_maker: protocols.NoticeMsgMaker
    ) -> None:
        with pytest.raises(re.error):
            msg_maker(pattern="asdf[")

    def test_it_says_its_not_plain(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert not msg_maker(pattern="one").is_plain

    def test_it_creates_new_regex_on_clone(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="two")
        clone = msg.clone(pattern="three")
        assert isinstance(clone, type(msg))
        assert isinstance(clone, notices.RegexMsg)
        assert clone.raw == "three"
        assert clone.regex.pattern == "three"

    def test_it_matches_with_regex(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="one.*")
        assert msg.match(want="one.*")
        assert msg.match(want="one")
        assert msg.match(want="one_")
        assert not msg.match(want="two")

        msg = msg_maker(pattern="one.+")
        assert not msg.match(want="one")
        assert msg.match(want="onea")
        assert msg.match(want="oneb")


class TestGlobMsg:
    @pytest.fixture
    def msg_maker(self) -> protocols.NoticeMsgMaker:
        return notices.GlobMsg.create

    class TestBaseFeatures(_BaseNoticeTests):
        pass

    def test_it_has_a_constructor(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert msg_maker == notices.GlobMsg.create
        msg = msg_maker(pattern="hi")
        assert isinstance(msg, notices.GlobMsg)
        assert msg.raw == "hi"

    def test_it_says_its_not_plain(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        assert not msg_maker(pattern="one").is_plain

    def test_it_matches_with_glob(self, msg_maker: protocols.NoticeMsgMaker) -> None:
        msg = msg_maker(pattern="one.*")
        assert not msg.match(want="one")
        assert msg.match(want="one.*")
        assert msg.match(want="one.")
        assert msg.match(want="one._")
        assert msg.match(want="one._sdf")
        assert not msg.match(want="two")

        msg = msg_maker(pattern="one.+")
        assert not msg.match(want="one")
        assert not msg.match(want="onea")
        assert not msg.match(want="oneb")
