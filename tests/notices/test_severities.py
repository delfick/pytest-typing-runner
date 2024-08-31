import dataclasses
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
        assert notices.NoteSeverity() != notices.ErrorSeverity("arg-type")


class TestWarningSeverity:
    def test_it_displays_note(self) -> None:
        sev = notices.WarningSeverity()
        assert sev.display == "warning"

    def test_it_is_ordable(self) -> None:
        sev_c = OtherSeverity("c")
        sev_a = OtherSeverity("a")
        sev_z = OtherSeverity("z")
        sev_y = OtherSeverity("y")
        sev_w1 = notices.WarningSeverity()
        sev_w2 = notices.WarningSeverity()
        original: Sequence[protocols.Severity] = [sev_c, sev_w1, sev_a, sev_z, sev_w2, sev_y]
        assert sorted(original) == [sev_a, sev_c, sev_w1, sev_w2, sev_y, sev_z]

    def test_it_can_be_compared(self) -> None:
        assert notices.WarningSeverity() == notices.WarningSeverity()
        assert notices.WarningSeverity() == OtherSeverity("warning")
        assert notices.WarningSeverity() != OtherSeverity("other")
        assert notices.WarningSeverity() != notices.ErrorSeverity("arg-type")


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
