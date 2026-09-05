from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

SAFE_NAMESPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}/[0-9a-f]{32}-[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    namespace: str
    path: Path
    object_name: str
    sha256: str
    size_bytes: int


class PosixArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.staging = self.root / "staging"
        self.objects = self.root / "objects"
        self.staging.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _namespace(value: str) -> str:
        if not SAFE_NAMESPACE.fullmatch(value):
            raise ValueError("invalid opaque artifact namespace")
        return value

    def stage(self, namespace: str, data: bytes, *, expected_sha256: str | None = None) -> StagedArtifact:
        namespace = self._namespace(namespace)
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("artifact digest mismatch")
        descriptor, raw_path = tempfile.mkstemp(prefix=f"{namespace}-", suffix=".stage", dir=self.staging)
        path = Path(raw_path)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StagedArtifact(namespace, path, f"{uuid4().hex}-{digest}", digest, len(data))

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def promote(self, staged: StagedArtifact) -> str:
        namespace_dir = self.objects / staged.namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)
        destination = namespace_dir / staged.object_name
        os.replace(staged.path, destination)
        self._fsync_directory(namespace_dir)
        self._fsync_directory(self.objects)
        return f"{staged.namespace}/{staged.object_name}"

    def put(self, namespace: str, data: bytes, *, expected_sha256: str | None = None) -> str:
        return self.promote(self.stage(namespace, data, expected_sha256=expected_sha256))

    def _path(self, key: str) -> Path:
        if not SAFE_KEY.fullmatch(key):
            raise ValueError("invalid opaque artifact key")
        path = (self.objects / key).resolve()
        if self.objects not in path.parents:
            raise ValueError("artifact key escapes store")
        return path

    def get(self, key: str) -> bytes:
        path = self._path(key)
        data = path.read_bytes()
        expected = key.rsplit("-", 1)[1]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("stored artifact digest mismatch")
        return data

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        self._fsync_directory(path.parent)

    def probe_writable(self) -> bool:
        staged = self.stage("health", b"review-platform-ready")
        try:
            return staged.path.read_bytes() == b"review-platform-ready"
        finally:
            staged.path.unlink(missing_ok=True)
            self._fsync_directory(self.staging)

    def collect_staging(self, *, older_than_seconds: float) -> list[str]:
        threshold = time.time() - older_than_seconds
        removed = []
        for path in self.staging.iterdir():
            if path.is_file() and path.stat().st_mtime <= threshold:
                path.unlink()
                removed.append(path.name)
        return sorted(removed)

    def collect_promoted(self, is_referenced, *, older_than_seconds: float) -> list[str]:  # type: ignore[no-untyped-def]
        threshold = time.time() - older_than_seconds
        removed: list[str] = []
        for namespace in self.objects.iterdir():
            if not namespace.is_dir():
                continue
            for path in namespace.iterdir():
                if path.stat().st_mtime > threshold:
                    continue
                key = f"{namespace.name}/{path.name}"
                digest = path.name.rsplit("-", 1)[1]
                try:
                    referenced = is_referenced(key, digest)
                except Exception:
                    continue
                if not referenced:
                    path.unlink()
                    removed.append(key)
        return sorted(removed)
