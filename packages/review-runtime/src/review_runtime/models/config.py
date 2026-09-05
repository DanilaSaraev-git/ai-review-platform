from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit


class SecretProvider(Protocol):
    def resolve(self, reference: str) -> str: ...


class EnvironmentSecretProvider:
    def resolve(self, reference: str) -> str:
        value = os.environ.get(reference)
        if value is None:
            raise ValueError("model credential reference is unavailable")
        return value


@dataclass(frozen=True, slots=True)
class FileSecretProvider:
    """Resolve one configured reference from a mounted, non-environment file."""

    reference: str
    path: Path

    def resolve(self, reference: str) -> str:
        if reference != self.reference:
            raise ValueError("model credential reference is unavailable")
        try:
            value = self.path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise ValueError("model credential file is unavailable") from error
        if not value:
            raise ValueError("model credential file is empty")
        return value


@dataclass(frozen=True, slots=True)
class EndpointPolicy:
    endpoint: str
    allowed_addresses: frozenset[str] = frozenset()

    def validate(self) -> str:
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("model endpoint must be an exact HTTP(S) origin/path without query")
        if parsed.username or parsed.password:
            raise ValueError("model endpoint cannot contain credentials")
        return self.endpoint

    def validate_resolved(
        self,
        resolver: Callable[..., Sequence[tuple[Any, ...]]] | None = None,
    ) -> str:
        """Resolve only at an explicit network boundary, never during config parsing."""
        endpoint = self.validate()
        if not self.allowed_addresses:
            return endpoint
        parsed = urlsplit(endpoint)
        resolve = resolver or socket.getaddrinfo
        addresses = {item[4][0] for item in resolve(parsed.hostname, parsed.port or 443)}
        normalized = {str(ipaddress.ip_address(address)) for address in addresses}
        if not normalized <= self.allowed_addresses:
            raise ValueError("model endpoint DNS resolves outside the configured allowlist")
        return endpoint
