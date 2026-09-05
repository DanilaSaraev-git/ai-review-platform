from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResourceRef(StrictDTO):
    id: str
    version: str


class CreateReviewRunDTO(StrictDTO):
    document_id: str
    context_document_ids: list[str] = Field(max_length=50)
    profile: ResourceRef
    model_profile: ResourceRef
    locale: str


class CreateReviewProfileDTO(StrictDTO):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=500)
    goal: str = Field(min_length=1, max_length=2000)
    checks: list[str] = Field(min_length=1)
    supersedes: ResourceRef | None = None


class CreateDialogueTurnDTO(StrictDTO):
    message: str = Field(min_length=1, max_length=20_000)
    expected_revision: int = Field(ge=0)


class RetryDialogueTurnDTO(StrictDTO):
    expected_revision: int = Field(ge=0)


class PutFindingDecisionDTO(StrictDTO):
    status: str
    reason: str | None
    resolution: str | None
    expected_revision: int = Field(ge=0)
