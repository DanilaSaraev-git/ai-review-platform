from review_worker import procrastinate_app


def test_procrastinate_app_exports_attempt_specific_tasks() -> None:
    assert "review.execute_review" in procrastinate_app.tasks
    assert "review.generate_dialogue" in procrastinate_app.tasks
