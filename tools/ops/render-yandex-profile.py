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
    template = root / "deploy/compose/config/model-profile.yandex-deepseek.json"
    profile = json.loads(template.read_text(encoding="utf-8"))
    profile["model"] = profile["model"].replace("${YANDEX_FOLDER_ID}", folder_id)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as f:
        temporary = Path(f.name)
        json.dump(profile, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporary, output)
    print(f"Profile saved: {output}; no provider request was made")


if __name__ == "__main__":
    main()
