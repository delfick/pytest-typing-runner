import pytest

from pytest_typing_runner import protocols, scenarios


class TestRunCleaners:
    def test_it_can_add_and_iterate_cleaners(self) -> None:
        cleaners = scenarios.RunCleaners()
        called: list[str] = []

        def make_cleaner(msg: str) -> protocols.RunCleaner:
            def clean() -> None:
                called.append(msg)

            return clean

        cleaners.add("b", make_cleaner("1"))
        cleaners.add("c", make_cleaner("3"))
        cleaners.add("a", make_cleaner("2"))

        all_cleans = iter(cleaners)
        assert called == []

        next(all_cleans)()
        assert called == ["1"]

        next(all_cleans)()
        assert called == ["1", "3"]

        next(all_cleans)()
        assert called == ["1", "3", "2"]

        with pytest.raises(StopIteration):
            next(all_cleans)

    def test_it_can_override_cleaners(self) -> None:
        cleaners = scenarios.RunCleaners()
        called: list[str] = []

        def make_cleaner(msg: str) -> protocols.RunCleaner:
            def clean() -> None:
                called.append(msg)

            return clean

        cleaners.add("b", make_cleaner("1"))
        cleaners.add("c", make_cleaner("3"))
        cleaners.add("a", make_cleaner("2"))
        cleaners.add("b", make_cleaner("4"))

        all_cleans = iter(cleaners)
        assert called == []

        next(all_cleans)()
        assert called == ["4"]

        next(all_cleans)()
        assert called == ["4", "3"]

        next(all_cleans)()
        assert called == ["4", "3", "2"]

        with pytest.raises(StopIteration):
            next(all_cleans)
