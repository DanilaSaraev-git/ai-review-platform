from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from review_runtime.poc_adapter.mapping import map_legacy_run


class PocReadError(ValueError):
    pass


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise PocReadError("legacy JSON contains a duplicate key")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(PocReadError("non-finite JSON number")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PocReadError("legacy run contains unreadable JSON") from error
    if not isinstance(value, dict):
        raise PocReadError("legacy artifact must be a JSON object")
    return value


def _inside(run: Path, relative: str) -> Path:
    candidate = (run / relative).resolve()
    if run != candidate and run not in candidate.parents:
        raise PocReadError("legacy artifact path escapes run directory")
    return candidate


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_poc_v1(run_directory: Path, *, schema_path: Path | None = None) -> dict[str, Any]:
    run = run_directory.resolve()
    if not run.is_dir():
        raise PocReadError("legacy run directory does not exist")
    before = {path.relative_to(run).as_posix(): _hash(path) for path in run.rglob("*") if path.is_file()}
    required = ("manifest.json", "bundle.json", "profile.json", "settings.json", "report.json")
    if any(name not in before for name in required):
        raise PocReadError("legacy run is incomplete")
    manifest = read_json(run / "manifest.json")
    bundle = read_json(run / "bundle.json")
    profile = read_json(run / "profile.json")
    settings = read_json(run / "settings.json")
    report = read_json(run / "report.json")
    if any(value.get("schema_version") != 1 for value in (manifest, bundle, profile, settings, report)):
        raise PocReadError("unsupported legacy schema version")
    if (
        manifest.get("run_id") != run.name
        or bundle.get("run_id") != run.name
        or report.get("run_id") != run.name
    ):
        raise PocReadError("legacy run identities do not match")
    for relative, digest in manifest.get("artifacts", {}).items():
        path = _inside(run, relative)
        if not path.is_file() or _hash(path) != digest:
            raise PocReadError("legacy artifact digest mismatch")
    raw_by_source: dict[str, dict[str, Any]] = {}
    for source in manifest.get("sources", []):
        status = source.get("status")
        if status == "unavailable":
            if any(source.get(key) is not None for key in ("snapshot", "sha256", "parser", "raw")):
                raise PocReadError("unavailable source contains fabricated metadata")
            continue
        if status not in {"available", "partial"}:
            raise PocReadError("legacy source status is invalid")
        if not all(source.get(key) for key in ("snapshot", "sha256", "parser", "raw")):
            raise PocReadError("available source lacks verified metadata")
        snapshot = _inside(run, source["snapshot"])
        if not snapshot.is_file() or _hash(snapshot) != source["sha256"]:
            raise PocReadError("legacy source digest mismatch")
        raw_by_source[source["id"]] = read_json(_inside(run, source["raw"]))
    run_digest = hashlib.sha256(
        "".join(f"{key}\0{value}\n" for key, value in sorted(before.items())).encode()
    ).hexdigest()
    view = map_legacy_run(
        manifest=manifest,
        bundle=bundle,
        profile=profile,
        report=report,
        raw_by_source=raw_by_source,
        run_digest=run_digest,
        schema_path=schema_path,
    )
    after = {path.relative_to(run).as_posix(): _hash(path) for path in run.rglob("*") if path.is_file()}
    if before != after:
        raise PocReadError("legacy run changed while being read")
    return view
