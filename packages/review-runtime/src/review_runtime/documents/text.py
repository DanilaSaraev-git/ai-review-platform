from __future__ import annotations

import hashlib
from typing import Any


class TextDocumentParser:
    name = "text-blocks"
    version = "1.0.0"
    settings_digest = hashlib.sha256(b"text-blocks-v1:nfc:bom-once:paragraphs").hexdigest()

    def parse(self, data: bytes, *, source_id: str, document_id: str) -> list[dict[str, Any]]:
        text = data.decode("utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        if not text.strip():
            raise ValueError("Primary document has no usable text fragments.")
        fragments: list[dict[str, Any]] = []
        cursor = 0
        for block in [item.strip() for item in text.split("\n\n") if item.strip()]:
            start = text.find(block, cursor)
            cursor = start + len(block)
            line_start = text.count("\n", 0, start) + 1
            line_end = line_start + block.count("\n")
            ordinal = len(fragments) + 1
            fragments.append(
                {
                    "id": f"{document_id}:{source_id}:fragment:{ordinal}",
                    "source_id": source_id,
                    "document_id": document_id,
                    "ordinal": ordinal,
                    "kind": "text",
                    "text": block,
                    "content_sha256": hashlib.sha256(block.encode()).hexdigest(),
                    "location": {
                        "kind": "text",
                        "line_start": line_start,
                        "line_end": line_end,
                        "char_start": 0,
                        "char_end": len(block),
                    },
                }
            )
        return fragments
