from __future__ import annotations

from typing import Any


def validate_mapped_view(view: dict[str, Any]) -> None:
    sources = {source["source_id"]: source for source in view["sources"]}
    fragments = {fragment["id"]: fragment for fragment in view["fragments"]}
    primary = [source for source in sources.values() if source["role"] == "document"]
    if len(primary) != 1 or not primary[0]["fragment_ids"]:
        raise ValueError("mapped view needs one usable primary source")
    target = view["coverage"]["target_fragment_ids"]
    if target != primary[0]["fragment_ids"]:
        raise ValueError("coverage target is not the exact primary fragment order")
    accounted = set(view["coverage"]["reviewed_fragment_ids"])
    accounted.update(gap["fragment_id"] for gap in view["coverage"]["gaps"] if gap["fragment_id"])
    if accounted != set(target):
        raise ValueError("primary coverage is not an exact partition")
    finding_ids = {finding["id"] for finding in view["findings"]}
    if {state["finding_id"] for state in view["finding_states"]} != finding_ids:
        raise ValueError("finding states are not one-to-one")
    for finding in view["findings"]:
        if finding["kind"] == "missing":
            if finding["anchors"] or not finding["scope"]:
                raise ValueError("missing finding must use primary scope")
        elif not finding["anchors"]:
            raise ValueError("non-missing finding needs evidence")
        for anchor in finding["anchors"]:
            fragment = fragments.get(anchor["fragment_id"])
            if fragment is None or fragment["source_id"] != anchor["source_id"]:
                raise ValueError("finding anchor is foreign")
            if fragment["text"][anchor["quote_start"] : anchor["quote_end"]] != anchor["quote"]:
                raise ValueError("finding quote offsets are invalid")
