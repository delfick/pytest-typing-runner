from typing import Protocol, TypedDict

from typing_extensions import NotRequired, Unpack

from pytest_typing_runner import notices


class _Comparable(Protocol):
    def __eq__(self, o: object, /) -> bool: ...


class MatchNotice:
    got: object

    class _Compare(TypedDict):
        location: NotRequired[_Comparable]
        line_number: NotRequired[_Comparable]
        col: NotRequired[_Comparable | None]
        severity: NotRequired[_Comparable]
        msg: NotRequired[_Comparable]
        display: NotRequired[_Comparable]

    def __init__(self, **check: Unpack[_Compare]) -> None:
        assert check, "Must have at least one property to check"
        self._check = check
        if isinstance(msg := self._check.get("msg"), str):
            self._check["msg"] = notices.PlainMsg.create(pattern=msg)
        self.missing_attr: set[str] = set()
        self.wrong_attr: dict[str, tuple[object, object]] = {}

    def __eq__(self, o: object) -> bool:
        self.got = o
        self.missing_attr.clear()
        self.wrong_attr.clear()
        for attr, right in self._check.items():
            if not hasattr(o, attr):
                self.missing_attr.add(attr)
            else:
                left = getattr(o, attr)
                if attr == "display" and callable(left):
                    left = left()

                if attr == "msg" and not isinstance(left, str) and right is not None:
                    if isinstance(right, str):
                        if not left.match(want=right):
                            self.wrong_attr[attr] = (left, right)
                        continue
                    elif getattr(right, "is_plain", False) and isinstance(
                        want := getattr(right, "raw", None), str
                    ):
                        if not left.match(want=want):
                            self.wrong_attr[attr] = (left, right)
                        continue

                if left != right:
                    self.wrong_attr[attr] = (left, right)

        return not self.missing_attr and not self.wrong_attr

    def __repr__(self) -> str:
        if not hasattr(self, "got"):
            return f"<MatchNotice({self._check})>"

        return repr(self.got)


class MatchNote(MatchNotice):
    class _Compare(TypedDict):
        location: NotRequired[_Comparable]
        line_number: NotRequired[_Comparable]
        col: NotRequired[_Comparable | None]
        msg: NotRequired[_Comparable]

    def __init__(self, **check: Unpack[_Compare]) -> None:
        assert "severity" not in check
        super().__init__(**{**check, "severity": notices.NoteSeverity()})
