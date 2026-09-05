from tests.contract.test_dialogue_decision_http import (
    test_dialogue_turn_replay_decision_cas_and_report_immutability,
)


async def test_exact_report_survives_dialogue_and_decision() -> None:
    await test_dialogue_turn_replay_decision_cas_and_report_immutability()
