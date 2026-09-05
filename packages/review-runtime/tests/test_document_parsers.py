from __future__ import annotations

import pytest
from review_runtime.documents.pdf import PdfDocumentParser
from review_runtime.documents.text import TextDocumentParser

from tests.fixtures.builders.documents import corrupt_pdf, minimal_pdf, text_document


def test_text_parser_removes_one_bom_and_has_stable_fragments() -> None:
    parser = TextDocumentParser()
    data = text_document("# Header\n\nFirst rule.\n\nSecond rule.", bom=True)
    first = parser.parse(data, source_id="source-main", document_id="doc")
    second = parser.parse(data, source_id="source-main", document_id="doc")
    assert first == second
    assert [item["ordinal"] for item in first] == [1, 2, 3]
    assert not first[0]["text"].startswith("\ufeff")


def test_pdf_parser_extracts_text_layer_with_page_locator() -> None:
    fragments = PdfDocumentParser().parse(
        minimal_pdf("Synthetic PDF requirement"), source_id="source-main", document_id="doc"
    )
    assert fragments
    assert fragments[0]["location"]["kind"] == "pdf"
    assert fragments[0]["location"]["page"] == 1


@pytest.mark.parametrize("data", [corrupt_pdf(), b"%PDF-1.4\n/Encrypt true"])
def test_broken_or_encrypted_pdf_has_no_usable_primary(data: bytes) -> None:
    with pytest.raises(ValueError):
        PdfDocumentParser().parse(data, source_id="source-main", document_id="doc")
