import textwrap

import pytest

from pytest_typing_runner import (
    expectations,
    notice_changers,
    notices,
    protocols,
    runners,
    scenarios,
    strategies,
)


@pytest.fixture(scope="module")
def strategy_register() -> protocols.StrategyRegistry:
    return strategies.StrategyRegistry.discover()


@pytest.fixture(
    params=[
        pytest.param(("MYPY_INCREMENTAL", True), id="incremental_same"),
        pytest.param(("MYPY_INCREMENTAL", False), id="incremental_external"),
        pytest.param(("MYPY_NO_INCREMENTAL", True), id="no_incremental_same"),
        pytest.param(("MYPY_NO_INCREMENTAL", False), id="no_incremental_external"),
        pytest.param(("MYPY_DAEMON", False), id="daemon"),
    ],
)
def typing_runner_config(
    strategy_register: protocols.StrategyRegistry, request: pytest.FixtureRequest
) -> protocols.RunnerConfig:
    strategy_maker = strategy_register.get_strategy(name=request.param[0])
    assert strategy_maker is not None
    return scenarios.RunnerConfig(
        same_process=request.param[1], typing_strategy=strategy_maker[1]()
    )


def test_works_with_low_level_verbose_api(
    typing_scenario_runner: protocols.ScenarioRunner[protocols.Scenario],
) -> None:
    typing_scenario_runner.file_modification(
        "main.py",
        textwrap.dedent("""
        a: int = 1
        reveal_type(a)
        """),
    )

    expect_notices = notice_changers.BulkAdd(
        root_dir=typing_scenario_runner.scenario.root_dir,
        add={
            "main.py": {3: [notices.ProgramNotice.reveal_msg("builtins.int")]},
        },
    )(typing_scenario_runner.generate_program_notices())

    def setup_expectations(
        options: protocols.RunOptions[protocols.Scenario],
    ) -> protocols.ExpectationsMaker[protocols.Scenario]:
        return lambda: expectations.Expectations[protocols.Scenario](
            expect_fail=False, expect_stderr="", expect_notices=expect_notices
        )

    # Run, expect success with one reveal
    options = runners.RunOptions.create(typing_scenario_runner)
    typing_scenario_runner.run_and_check(setup_expectations=setup_expectations, options=options)

    typing_scenario_runner.file_modification(
        "main.py",
        textwrap.dedent("""
        a: int = 1
        reveal_type(a)

        a = "asdf"
        """),
    )

    expect_notices = notice_changers.BulkAdd(
        root_dir=typing_scenario_runner.scenario.root_dir,
        add={
            "main.py": {
                5: [
                    (
                        notices.ErrorSeverity("assignment"),
                        'Incompatible types in assignment (expression has type "str", variable has type "int")',
                    )
                ]
            }
        },
    )(expect_notices)

    def setup_expectations2(
        options: protocols.RunOptions[protocols.Scenario],
    ) -> protocols.ExpectationsMaker[protocols.Scenario]:
        return lambda: expectations.Expectations[protocols.Scenario](
            expect_fail=True, expect_stderr="", expect_notices=expect_notices
        )

    typing_scenario_runner.run_and_check(setup_expectations=setup_expectations2, options=options)

    expect_notices = notice_changers.BulkAdd(
        root_dir=typing_scenario_runner.scenario.root_dir,
        add={"a.py": {50: [(notices.ErrorSeverity("arg-type"), "hi")]}},
    )(expect_notices)

    expected = textwrap.dedent("""
    > a.py
      | ✘ 50:
      | ✘ !! GOT  !! <NONE>
      |   !! WANT !! severity=error[arg-type]:: hi
    > main.py
      | ✓ 3: severity=note:: Revealed type is "builtins.int"
      | ✓ 5: severity=error[assignment]:: Incompatible types in assignment (expression has type "str", variable has type "int")
    """).strip()

    with pytest.raises(AssertionError) as e:
        typing_scenario_runner.run_and_check(
            setup_expectations=setup_expectations, options=options
        )

    assert str(e.value).strip() == expected
