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
