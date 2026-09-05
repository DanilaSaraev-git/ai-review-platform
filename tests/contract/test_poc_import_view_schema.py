from pathlib import Path

from tests.contract.contract_helpers import load_json_no_duplicates


def test_poc_contract_is_typed_view_not_public_http_api() -> None:
    root = Path(__file__).parents[2]
    schema = load_json_no_duplicates(
        root / "specs/003-backend-implementation/contracts/poc-import-view.v1.schema.json"
    )
    assert schema["properties"]["schema_version"]["const"] == "poc-import-view.v1"
    assert "paths" not in schema
