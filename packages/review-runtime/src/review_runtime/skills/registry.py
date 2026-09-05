from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from jsonschema import Draft202012Validator
from review_core.canonical import digest_value

_ENGINE_REQUIREMENT = re.compile(r"^>=(\d+)\.(\d+)\.(\d+)$")
_ENGINE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True, slots=True)
class SkillFile:
    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class ResolvedSkill:
    package: Path
    manifest: dict[str, Any]
    manifest_digest: str
    package_digest: str
    legacy_digest: str
    files: MappingProxyType[str, SkillFile]


class SkillRegistry:
    def __init__(
        self,
        manifest_schema: Path,
        *,
        engine_version: str = "0.1.0",
        model_capabilities: set[str] | frozenset[str] = frozenset({"text_generation"}),
    ) -> None:
        self.schema = json.loads(manifest_schema.read_text())
        self.engine_version = self._version(engine_version)
        self.model_capabilities = frozenset(model_capabilities)
        self._resolved_identities: dict[tuple[str, str], str] = {}

    def load(self, package: Path) -> dict[str, Any]:
        return self.resolve(package).manifest

    def resolve(self, package: Path) -> ResolvedSkill:
        manifest = json.loads((package / "manifest.json").read_text())
        Draft202012Validator(self.schema).validate(manifest)
        declared = {item["path"]: item["sha256"] for item in manifest["files"]}
        required = set(manifest["references"]) | {
            manifest["operations"]["review"]["instructions"],
            manifest["operations"]["finding_dialogue"]["instructions"],
        }
        actual_inventory = {
            path.relative_to(package).as_posix()
            for path in package.rglob("*")
            if path.is_file() and path.relative_to(package).as_posix() != "manifest.json"
        }
        if required != set(declared) or actual_inventory != set(declared):
            raise ValueError("skill manifest file inventory is not exact")
        files: dict[str, SkillFile] = {}
        for relative, expected in declared.items():
            target = (package / relative).resolve()
            if package.resolve() not in target.parents:
                raise ValueError("skill path escapes package")
            content = target.read_bytes()
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected:
                raise ValueError("skill package digest drift")
            files[relative] = SkillFile(path=relative, content=content, sha256=actual)
        self._validate_requirements(manifest)
        package_digest = self.package_digest(package, manifest)
        identity = (str(manifest["id"]), str(manifest["version"]))
        previous = self._resolved_identities.setdefault(identity, package_digest)
        if previous != package_digest:
            raise ValueError("skill identity drift: the same id/version resolved to different contents")
        return ResolvedSkill(
            package=package.resolve(),
            manifest=cast(dict[str, Any], manifest),
            manifest_digest=digest_value(self._semantic_manifest(manifest)),
            package_digest=package_digest,
            legacy_digest=self.legacy_package_digest(package, manifest),
            files=MappingProxyType(files),
        )

    @staticmethod
    def package_digest(package: Path, manifest: dict[str, Any]) -> str:
        inventory = [
            {
                "path": item["path"],
                "sha256": hashlib.sha256((package / item["path"]).read_bytes()).hexdigest(),
            }
            for item in sorted(manifest["files"], key=lambda value: value["path"])
        ]
        return digest_value(
            {"manifest": SkillRegistry._semantic_manifest(manifest), "file_digests": inventory}
        )

    @staticmethod
    def legacy_package_digest(package: Path, manifest: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        for item in sorted(manifest["files"], key=lambda value: value["path"]):
            digest.update(item["path"].encode() + b"\0" + (package / item["path"]).read_bytes())
        return digest.hexdigest()

    def matches_snapshot(self, package: Path, manifest: dict[str, Any], expected_digest: str) -> bool:
        return expected_digest in {
            self.package_digest(package, manifest),
            self.legacy_package_digest(package, manifest),
        }

    def _validate_requirements(self, manifest: dict[str, Any]) -> None:
        minimum = _ENGINE_REQUIREMENT.fullmatch(manifest["requires"]["engine"])
        if minimum is None or self.engine_version < tuple(int(value) for value in minimum.groups()):
            raise ValueError("skill engine requirement is not satisfied")
        required = set(manifest["requires"]["model_capabilities"])
        missing = required - self.model_capabilities
        if missing:
            raise ValueError(f"skill model capabilities are not satisfied: {sorted(missing)}")

    @staticmethod
    def _semantic_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
        normalized = cast(dict[str, Any], json.loads(json.dumps(manifest)))
        normalized["files"] = sorted(normalized["files"], key=lambda value: value["path"])
        normalized["requires"]["model_capabilities"] = sorted(
            normalized["requires"]["model_capabilities"]
        )
        return normalized

    @staticmethod
    def _version(value: str) -> tuple[int, int, int]:
        match = _ENGINE_VERSION.fullmatch(value)
        if match is None:
            raise ValueError("engine version must be semantic version")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
