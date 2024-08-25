import pathlib
import textwrap

from pytest_typing_runner import notices, parse


class TestParseNotices:
    def test_it_can_replace_code_when_reveal_is_found(self, tmp_path: pathlib.Path) -> None:
        original = textwrap.dedent("""
        model: type[Leader] = Follow1
        # ^ REVEAL[one] ^ type[leader.models.Leader]

        class Thing:
            def __init__(self, model: type[Leader]) -> None:
                self.model = model

        found = Concrete.cast_as_concrete(Thing(model=model).model)
        # ^ REVEAL[two] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

        reveal_type(found)
        # ^ REVEAL[three] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

        if True:
            reveal_type(found)
            # ^ REVEAL[four] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

            thing = Thing(model=model)
            found = Concrete.cast_as_concrete(thing.model)
            # ^ REVEAL[five] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        """)

        path = "fle.py"
        location = tmp_path / path

        transformed = textwrap.dedent("""
        model: type[Leader] = Follow1
        reveal_type(model)
        # ^ REVEAL[one] ^ type[leader.models.Leader]

        class Thing:
            def __init__(self, model: type[Leader]) -> None:
                self.model = model

        found = Concrete.cast_as_concrete(Thing(model=model).model)
        reveal_type(found)
        # ^ REVEAL[two] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

        reveal_type(found)
        # ^ REVEAL[three] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

        if True:
            reveal_type(found)
            # ^ REVEAL[four] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]

            thing = Thing(model=model)
            found = Concrete.cast_as_concrete(thing.model)
            reveal_type(found)
            # ^ REVEAL[five] ^ Union[type[simple.models.Follow1], type[simple.models.Follow2]]
        """)

        expected = notices.FileNotices(
            location=location,
            by_line_number={
                3: notices.LineNotices(
                    line_number=3,
                    location=location,
                    notices=[
                        notices.ProgramNotice(
                            location=location,
                            line_number=3,
                            col=None,
                            severity=notices.NoteSeverity(),
                            msg=notices.ProgramNotice.reveal_msg("type[leader.models.Leader]"),
                        )
                    ],
                ),
                11: notices.LineNotices(
                    line_number=11,
                    location=location,
                    notices=[
                        notices.ProgramNotice(
                            location=location,
                            line_number=11,
                            col=None,
                            severity=notices.NoteSeverity(),
                            msg=notices.ProgramNotice.reveal_msg(
                                "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                            ),
                        )
                    ],
                ),
                14: notices.LineNotices(
                    line_number=14,
                    location=location,
                    notices=[
                        notices.ProgramNotice(
                            location=location,
                            line_number=14,
                            col=None,
                            severity=notices.NoteSeverity(),
                            msg=notices.ProgramNotice.reveal_msg(
                                "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                            ),
                        )
                    ],
                ),
                18: notices.LineNotices(
                    line_number=18,
                    location=location,
                    notices=[
                        notices.ProgramNotice(
                            location=location,
                            line_number=18,
                            col=None,
                            severity=notices.NoteSeverity(),
                            msg=notices.ProgramNotice.reveal_msg(
                                "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                            ),
                        )
                    ],
                ),
                23: notices.LineNotices(
                    line_number=23,
                    location=location,
                    notices=[
                        notices.ProgramNotice(
                            location=location,
                            line_number=23,
                            col=None,
                            severity=notices.NoteSeverity(),
                            msg=notices.ProgramNotice.reveal_msg(
                                "Union[type[simple.models.Follow1], type[simple.models.Follow2]]"
                            ),
                        )
                    ],
                ),
            },
            name_to_line_number={"one": 3, "two": 11, "three": 14, "four": 18, "five": 23},
        )

        replaced, parsed = parse.FileContent().parse(
            original, into=notices.FileNotices(location=location)
        )
        assert replaced == transformed
        assert parsed == expected

        # And can run again with no further changes
        replaced, parsed = parse.FileContent().parse(replaced, into=parsed)
        assert replaced == transformed
        assert parsed == expected
