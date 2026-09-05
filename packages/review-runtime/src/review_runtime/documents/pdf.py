from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pdfplumber


class PdfDocumentParser:
    name = "pdfplumber-pages"
    version = "1.0.0"
    settings_digest = hashlib.sha256(b"pdfplumber-pages-v1:page-text:normalized-bbox").hexdigest()

    def parse(self, data: bytes, *, source_id: str, document_id: str) -> list[dict[str, Any]]:
        try:
            with pdfplumber.open(BytesIO(data)) as pdf:
                if getattr(pdf, "is_encrypted", False):
                    raise ValueError("Encrypted PDF is unsupported.")
                fragments: list[dict[str, Any]] = []
                for page_number, page in enumerate(pdf.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if not text:
                        continue
                    ordinal = len(fragments) + 1
                    fragments.append(
                        {
                            "id": f"{document_id}:{source_id}:fragment:{ordinal}",
                            "source_id": source_id,
                            "document_id": document_id,
                            "ordinal": ordinal,
                            "kind": "text",
                            "text": text,
                            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "location": {
                                "kind": "pdf",
                                "page": page_number,
                                "rects": [[0.0, 0.0, 1.0, 1.0]],
                                "table": None,
                                "row": None,
                            },
                        }
                    )
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("PDF is corrupt or cannot be extracted.") from error
        if not fragments:
            raise ValueError("Primary PDF has no usable text layer.")
        return fragments
