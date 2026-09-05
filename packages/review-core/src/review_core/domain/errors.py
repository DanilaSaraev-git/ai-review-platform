from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DomainError(Exception):
    code: str
    status: int
    title: str
    detail: str
    errors: list[dict[str, str]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.detail


class NotFound(DomainError):
    def __init__(self, detail: str = "Resource not found.") -> None:
        super().__init__("not_found", 404, "Resource not found", detail)


class Conflict(DomainError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(code, 409, "Conflict", detail)


class InvalidRequest(DomainError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(code, 400, "Invalid request", detail)


class PayloadTooLarge(DomainError):
    def __init__(self, detail: str = "Payload exceeds the configured limit.") -> None:
        super().__init__("payload_too_large", 413, "Payload too large", detail)
