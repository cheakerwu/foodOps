"""Tests for BrowserUseExecutionEvidence and OperationResult screenshot_paths."""

from __future__ import annotations

import json

from food_ops_demo.models import BrowserUseExecutionEvidence, OperationResult


class TestBrowserUseExecutionEvidence:
    """JSON round-trip and validation tests for BrowserUseExecutionEvidence."""

    def test_minimal_fields_roundtrip(self) -> None:
        """Only required fields should survive a JSON round-trip."""
        evidence = BrowserUseExecutionEvidence(
            success=True,
            operation_type="update_price",
            store_name="Test Store",
            target_name="Chicken Rice",
            expected_value="15.00",
        )
        data = evidence.model_dump()
        restored = BrowserUseExecutionEvidence.model_validate(data)
        assert restored == evidence

    def test_json_string_roundtrip(self) -> None:
        """Serialize to JSON string and deserialize back."""
        evidence = BrowserUseExecutionEvidence(
            success=False,
            operation_type="toggle_availability",
            store_name="Sushi Bar",
            target_name="Salmon Roll",
            expected_value="on_shelf",
            observed_value="off_shelf",
            final_url="https://merchant.example.com/store/123",
            evidence_text="Toggle did not change state",
            screenshot_paths=["/tmp/shot1.png", "/tmp/shot2.png"],
            error_code="TOGGLE_FAILED",
            error_message="Button click had no effect",
        )
        json_str = evidence.model_dump_json()
        restored = BrowserUseExecutionEvidence.model_validate_json(json_str)
        assert restored == evidence
        assert len(restored.screenshot_paths) == 2

    def test_default_values(self) -> None:
        """Optional fields should have correct defaults."""
        evidence = BrowserUseExecutionEvidence(
            success=True,
            operation_type="update_price",
            store_name="Store",
            target_name="Item",
            expected_value="10.00",
        )
        assert evidence.observed_value is None
        assert evidence.final_url is None
        assert evidence.evidence_text == ""
        assert evidence.screenshot_paths == []
        assert evidence.error_code is None
        assert evidence.error_message is None

    def test_screenshot_paths_immutable_on_copy(self) -> None:
        """Mutating a copy's screenshot_paths must not affect the original."""
        evidence = BrowserUseExecutionEvidence(
            success=True,
            operation_type="update_price",
            store_name="Store",
            target_name="Item",
            expected_value="10.00",
            screenshot_paths=["a.png"],
        )
        modified = evidence.model_copy(
            update={"screenshot_paths": ["a.png", "b.png"]}
        )
        assert evidence.screenshot_paths == ["a.png"]
        assert modified.screenshot_paths == ["a.png", "b.png"]

    def test_missing_required_field_raises(self) -> None:
        """Omitting a required field must raise a validation error."""
        import pytest

        with pytest.raises(Exception):
            BrowserUseExecutionEvidence(
                success=True,
                operation_type="update_price",
                # store_name missing
                target_name="Item",
                expected_value="10.00",
            )


class TestOperationResultScreenshotPaths:
    """Tests for the screenshot_paths field on OperationResult."""

    def test_default_screenshot_paths_empty(self) -> None:
        result = OperationResult(success=True)
        assert result.screenshot_paths == []

    def test_screenshot_paths_roundtrip(self) -> None:
        result = OperationResult(
            success=True,
            screenshot_paths=["/tmp/a.png", "/tmp/b.png"],
        )
        json_str = result.model_dump_json()
        restored = OperationResult.model_validate_json(json_str)
        assert restored == result
        assert len(restored.screenshot_paths) == 2

    def test_operation_result_with_evidence_and_screenshots(self) -> None:
        """Both evidence dict and screenshot_paths should coexist."""
        result = OperationResult(
            success=True,
            evidence={"detail": "ok"},
            screenshot_paths=["shot.png"],
        )
        data = result.model_dump()
        assert "evidence" in data
        assert "screenshot_paths" in data
        restored = OperationResult.model_validate(data)
        assert restored.evidence == {"detail": "ok"}
        assert restored.screenshot_paths == ["shot.png"]
