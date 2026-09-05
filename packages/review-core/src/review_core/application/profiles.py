from __future__ import annotations

from dataclasses import dataclass

from review_core.canonical import digest_value
from review_core.domain import ServerId


class ProfileConflict(ValueError):
    pass


class SystemProfileImmutable(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProfileVersion:
    id: str
    version: str
    scope: str
    digest: str
    name: str
    role: str
    goal: str
    checks: tuple[str, ...]
    supersedes: tuple[str, str] | None = None


class ProfileStore:
    def __init__(self) -> None:
        self._versions: dict[tuple[str, str], ProfileVersion] = {}
        self._heads: dict[str, str] = {}

    @staticmethod
    def _semantic(name: str, role: str, goal: str, checks: list[str]) -> dict[str, object]:
        if (
            not name.strip()
            or not role.strip()
            or not goal.strip()
            or not checks
            or len(checks) != len(set(checks))
        ):
            raise ValueError("profile semantic fields must be non-empty and checks unique")
        return {"name": name, "role": role, "goal": goal, "checks": checks}

    def create(
        self,
        *,
        name: str,
        role: str,
        goal: str,
        checks: list[str],
        supersedes: tuple[str, str] | None = None,
    ) -> ProfileVersion:
        semantic = self._semantic(name, role, goal, checks)
        digest = digest_value(semantic)
        if supersedes is None:
            family_id = str(ServerId.new())
            version = "1.0.0"
        else:
            family_id, prior_version = supersedes
            prior = self._versions.get((family_id, prior_version))
            if prior is None:
                raise KeyError("profile version not found")
            if prior.scope == "system":
                raise SystemProfileImmutable("system profile is immutable")
            if self._heads.get(family_id) != prior_version:
                raise ProfileConflict("stale profile family head")
            if prior.digest == digest:
                raise ProfileConflict("unchanged profile content")
            major, minor, patch = (int(part) for part in prior_version.split("."))
            version = f"{major}.{minor}.{patch + 1}"
        profile = ProfileVersion(
            id=family_id,
            version=version,
            scope="workspace",
            digest=digest,
            name=name,
            role=role,
            goal=goal,
            checks=tuple(checks),
            supersedes=supersedes,
        )
        self._versions[(family_id, version)] = profile
        self._heads[family_id] = version
        return profile

    def seed_system(
        self, *, name: str, role: str, goal: str, checks: list[str], profile_id: str | None = None
    ) -> ProfileVersion:
        semantic = self._semantic(name, role, goal, checks)
        profile = ProfileVersion(
            id=profile_id or str(ServerId.new()),
            version="1.0.0",
            scope="system",
            digest=digest_value(semantic),
            name=name,
            role=role,
            goal=goal,
            checks=tuple(checks),
        )
        self._versions[(profile.id, profile.version)] = profile
        self._heads[profile.id] = profile.version
        return profile

    def get(self, family_id: str, version: str) -> ProfileVersion:
        return self._versions[(family_id, version)]

    def list_heads(self) -> list[ProfileVersion]:
        return [self._versions[(family_id, version)] for family_id, version in self._heads.items()]
