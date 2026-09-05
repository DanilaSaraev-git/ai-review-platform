from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Protocol
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
class EndpointPolicy:
    endpoint: str
    allowed_addresses: frozenset[str] = frozenset()

    def validate(self) -> str:
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("model endpoint must be an exact HTTP(S) origin/path without query")
        if parsed.username or parsed.password:
            raise ValueError("model endpoint cannot contain credentials")
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        normalized = {str(ipaddress.ip_address(address)) for address in addresses}
        if self.allowed_addresses and not normalized <= self.allowed_addresses:
            raise ValueError("model endpoint DNS resolves outside the configured allowlist")
        return self.endpoint.rstrip("/")
