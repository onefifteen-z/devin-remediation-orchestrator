import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

Outcome = Literal["success", "blocked", "failed"]
TestResult = Literal["passed", "failed", "skipped", "not_run"]
TestCategory = Literal[
    "pre_fix_reproduction",
    "post_fix_validation",
    "regression_test",
    "general_test",
    "ci_validation",
]


class TestPerformed(BaseModel):
    command: str
    result: TestResult
    category: TestCategory | None = None


class RemediationResult(BaseModel):
    outcome: Outcome
    root_cause: str | None = None
    implementation_summary: str | None = None
    tests_performed: list[TestPerformed] = Field(default_factory=list)
    pr_url: str | None = None
    residual_risks: list[str] = Field(default_factory=list)
    blocker: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_status_field(cls, data: Any) -> Any:
        if isinstance(data, dict) and "outcome" not in data and "status" in data:
            data = dict(data)
            data["outcome"] = data.pop("status")
        return data

    @field_validator("residual_risks", mode="before")
    @classmethod
    def coerce_residual_risks(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]


REMEDIATION_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["outcome"],
    "properties": {
        "outcome": {
            "type": "string",
            "enum": ["success", "blocked", "failed"],
        },
        "root_cause": {"type": "string"},
        "implementation_summary": {"type": "string"},
        "tests_performed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["command", "result"],
                "properties": {
                    "command": {"type": "string"},
                    "result": {
                        "type": "string",
                        "enum": ["passed", "failed", "skipped", "not_run"],
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "pre_fix_reproduction",
                            "post_fix_validation",
                            "regression_test",
                            "general_test",
                            "ci_validation",
                        ],
                    },
                },
            },
        },
        "pr_url": {"type": ["string", "null"]},
        "residual_risks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "blocker": {"type": ["string", "null"]},
    },
}


def parse_remediation_result(
    raw: dict[str, Any] | None,
    *,
    devin_session_id: str | None = None,
) -> RemediationResult | None:
    if not raw:
        return None
    try:
        return RemediationResult.model_validate(raw)
    except Exception:
        logger.warning(
            "Unable to parse Devin structured_output",
            extra={"devin_session_id": devin_session_id},
        )
        return None


def remediation_result_to_db_fields(
    result: RemediationResult,
    raw: dict[str, Any],
) -> dict[str, Any]:
    import json

    structured_payload = {
        "tests_performed": [test.model_dump() for test in result.tests_performed],
        "residual_risks": result.residual_risks,
        "pr_url": result.pr_url,
        "raw": raw,
    }
    return {
        "remediation_outcome": result.outcome,
        "root_cause": result.root_cause,
        "implementation_summary": result.implementation_summary,
        "blocker": result.blocker,
        "structured_result_json": json.dumps(structured_payload),
    }
