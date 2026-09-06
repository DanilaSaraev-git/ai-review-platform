"""Render the non-secret Yandex model profile; never contact the provider."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder_id_file", type=Path)
    parser.add_argument("output", type=Path)
    templates = {
        "deepseek": "model-profile.yandex-deepseek.json",
        "qwen35b": "model-profile.yandex-qwen35b.json",
        "gpt-oss20b": "model-profile.yandex-gpt-oss20b.json",
    }
    parser.add_argument(
        "--model",
        action="append",
        choices=tuple(templates),
        help="Include this model; repeat for a model set. Default: deepseek.",
    )
    args = parser.parse_args()
    folder_id = args.folder_id_file.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{6,128}", folder_id) is None:
        parser.error("folder ID is invalid")
    if not args.output.is_absolute():
        parser.error("output must be an absolute path outside the repository")
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("store the deployment profile outside the repository")
    selected = args.model or ["deepseek"]
    if len(selected) != len(set(selected)):
        parser.error("each model may be included only once")
    profiles = []
    for model in selected:
        template = root / "deploy/compose/config" / templates[model]
        profile = json.loads(template.read_text(encoding="utf-8"))
        profile["model"] = profile["model"].replace("${YANDEX_FOLDER_ID}", folder_id)
        profiles.append(profile)
    rendered = profiles[0] if len(profiles) == 1 else {"profiles": profiles}
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as f:
        temporary = Path(f.name)
        json.dump(rendered, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporary, output)
    print(f"Profile saved: {output}; no provider request was made")


if __name__ == "__main__":
    main()
