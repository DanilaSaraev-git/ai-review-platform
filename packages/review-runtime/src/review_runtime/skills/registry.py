from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator


class SkillRegistry:
    def __init__(self, manifest_schema: Path) -> None:
        self.schema = json.loads(manifest_schema.read_text())

    def load(self, package: Path) -> dict[str, Any]:
        manifest = json.loads((package / "manifest.json").read_text())
        Draft202012Validator(self.schema).validate(manifest)
        declared = {item["path"]: item["sha256"] for item in manifest["files"]}
        required = set(manifest["references"]) | {
            manifest["operations"]["review"]["instructions"],
            manifest["operations"]["finding_dialogue"]["instructions"],
        }
        if required != set(declared):
            raise ValueError("skill manifest file inventory is not exact")
        for relative, expected in declared.items():
            target = (package / relative).resolve()
            if package.resolve() not in target.parents:
                raise ValueError("skill path escapes package")
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError("skill package digest drift")
        return cast(dict[str, Any], manifest)

    @staticmethod
    def package_digest(package: Path, manifest: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        for item in sorted(manifest["files"], key=lambda value: value["path"]):
            digest.update(item["path"].encode() + b"\0" + (package / item["path"]).read_bytes())
        return digest.hexdigest()
