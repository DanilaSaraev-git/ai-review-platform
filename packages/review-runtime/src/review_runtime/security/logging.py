from __future__ import annotations

import logging
import re
from typing import Any

SAFE_KEYS = {"request_id", "trace_id", "job_id", "resource_id", "state", "code", "count", "duration_ms"}
REDACTIONS = (
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"/(?:Users|home)/[^\s]+"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"),
    re.compile(
        r"(?i)([\"']?(?:authorization|api[-_]?key|token|credential(?:_path)?)[\"']?\s*[:=]\s*)"
        r"[\"']?[^\s,}\"']+[\"']?"
    ),
)


def safe_fields(**fields: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in fields.items()
        if key in SAFE_KEYS and isinstance(value, (str, int, float))
    }


class SafeLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in REDACTIONS:
            message = pattern.sub("[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True
