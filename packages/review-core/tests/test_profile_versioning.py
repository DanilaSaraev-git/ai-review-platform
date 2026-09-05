from __future__ import annotations

import pytest
from review_core.application.profiles import ProfileConflict, ProfileStore, SystemProfileImmutable

BASE = {"name": "Base", "role": "Analyst", "goal": "Find ambiguity", "checks": ["sources"]}


def test_profile_families_are_distinct_even_with_same_name() -> None:
    store = ProfileStore()
    first = store.create(**BASE)
    second = store.create(**BASE)
    assert first.id != second.id
    assert first.version == second.version == "1.0.0"


def test_profile_version_is_append_only_and_head_is_cas() -> None:
    store = ProfileStore()
    first = store.create(**BASE)
    second = store.create(**(BASE | {"goal": "Find testability gaps"}), supersedes=(first.id, "1.0.0"))
    assert second.id == first.id
    assert second.version == "1.0.1"
    assert store.get(first.id, "1.0.0") == first
    with pytest.raises(ProfileConflict, match="stale"):
        store.create(**(BASE | {"goal": "Other"}), supersedes=(first.id, "1.0.0"))
    with pytest.raises(ProfileConflict, match="unchanged"):
        store.create(**(BASE | {"goal": "Find testability gaps"}), supersedes=(second.id, second.version))


def test_system_profile_cannot_be_superseded() -> None:
    store = ProfileStore()
    profile = store.seed_system(**BASE)
    with pytest.raises(SystemProfileImmutable):
        store.create(**(BASE | {"goal": "Other"}), supersedes=(profile.id, profile.version))
