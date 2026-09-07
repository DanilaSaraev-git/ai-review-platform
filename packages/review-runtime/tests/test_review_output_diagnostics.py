import json
from pathlib import Path

import pytest
from review_runtime.reports import ModelReviewOutputError, ModelReviewOutputValidator

ROOT = Path(__file__).parents[3]


def test_schema_feedback_identifies_required_fields_without_leaking_model_values() -> None:
    validator = ModelReviewOutputValidator(
        ROOT / "specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json"
    )
    value = json.loads((ROOT / "tests/fixtures/ml-integration/review-response.json").read_text())
    del value["findings"][0]["priority"]
    value["findings"][0]["kind"] = "PRIVATE_MODEL_VALUE"
    value["PRIVATE_MODEL_KEY"] = "PRIVATE_MODEL_CONTENT"
    with pytest.raises(ModelReviewOutputError) as caught:
        validator.validate(value)
    feedback = caught.value.feedback
    assert "priority" in feedback
    assert "enum" in feedback
    assert "PRIVATE_MODEL" not in feedback
    assert "PRIVATE_MODEL" not in str(caught.value)
