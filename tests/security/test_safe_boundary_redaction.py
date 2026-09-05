import logging

from review_runtime.security.logging import SafeLogFilter, safe_fields


def test_safe_log_filter_redacts_secrets_paths_and_content_canaries() -> None:
    record = logging.LogRecord(
        "review", logging.INFO, __file__, 1, "token=%s path=%s", ("sk-secret", "/Users/private/doc.md"), None
    )
    assert SafeLogFilter().filter(record)
    message = record.getMessage()
    assert "sk-secret" not in message
    assert "/Users/" not in message


def test_safe_fields_allow_ids_codes_counts_and_durations_only() -> None:
    assert safe_fields(resource_id="id-1", code="completed", count=3, duration_ms=12) == {
        "resource_id": "id-1",
        "code": "completed",
        "count": 3,
        "duration_ms": 12,
    }
    assert "message" not in safe_fields(message="document content")
