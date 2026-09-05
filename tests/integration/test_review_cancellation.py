from review_core.domain.errors import Conflict


def test_terminal_report_wins_before_late_cancellation(client_platform) -> None:  # type: ignore[no-untyped-def]
    platform, run_id = client_platform
    try:
        platform.cancel_run(platform.workspace_id, run_id)
    except Conflict as error:
        assert error.code == "run_terminal"
    else:
        raise AssertionError("completed run accepted cancellation")
