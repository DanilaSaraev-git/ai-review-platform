from review_worker.handlers import finish_execution


def test_duplicate_delivery_cannot_finish_an_attempt_twice() -> None:
    execution = {"state": "running", "lease_token": "exact", "lease_owner": "worker"}
    assert finish_execution(execution, "exact")
    assert not finish_execution(execution, "exact")
