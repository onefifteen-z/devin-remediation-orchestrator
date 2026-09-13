from dataclasses import dataclass

from app.schemas.ci import CiCheckRunEvent, FailureType

TRANSIENT_CONCLUSIONS = frozenset({"cancelled", "timed_out", "stale"})

INFRA_SIGNALS = (
    "runner unavailable",
    "runner failure",
    "docker registry",
    "registry unavailable",
    "service unavailable",
    "resource unavailable",
    "connection refused",
    "setup failed",
    "infrastructure",
    "runner",
)

CODE_SIGNALS = (
    "pytest",
    "unittest",
    "unit test",
    "integration test",
    "lint",
    "eslint",
    "typescript",
    "typecheck",
    "build",
    "compile",
    "mypy",
    "ruff",
    "flake8",
    "jest",
    "vitest",
    "cargo test",
    "go test",
)


@dataclass(frozen=True)
class ClassificationResult:
    failure_type: FailureType
    reason: str


def _combined_text(event: CiCheckRunEvent) -> str:
    parts = [
        event.check_name or "",
        event.output_title or "",
        event.output_summary or "",
    ]
    return " ".join(parts).lower()


def _contains_signal(text: str, signals: tuple[str, ...]) -> str | None:
    for signal in signals:
        if signal in text:
            return signal
    return None


def classify(event: CiCheckRunEvent) -> ClassificationResult:
    conclusion = (event.conclusion or "").lower()
    text = _combined_text(event)

    if conclusion in TRANSIENT_CONCLUSIONS:
        return ClassificationResult(
            failure_type=FailureType.TRANSIENT_FAILURE,
            reason=f"conclusion={conclusion} indicates transient CI failure",
        )

    if conclusion == "startup_failure":
        return ClassificationResult(
            failure_type=FailureType.INFRA_FAILURE,
            reason="conclusion=startup_failure indicates infrastructure failure",
        )

    infra_signal = _contains_signal(text, INFRA_SIGNALS)
    if infra_signal:
        return ClassificationResult(
            failure_type=FailureType.INFRA_FAILURE,
            reason=f"infrastructure signal '{infra_signal}' in check output",
        )

    if conclusion == "failure":
        code_signal = _contains_signal(text, CODE_SIGNALS)
        if code_signal:
            return ClassificationResult(
                failure_type=FailureType.CODE_FAILURE,
                reason=f"code/test signal '{code_signal}' with conclusion=failure",
            )
        return ClassificationResult(
            failure_type=FailureType.UNKNOWN,
            reason="conclusion=failure without strong code/test evidence",
        )

    if conclusion == "action_required":
        return ClassificationResult(
            failure_type=FailureType.UNKNOWN,
            reason="conclusion=action_required requires manual intervention",
        )

    return ClassificationResult(
        failure_type=FailureType.UNKNOWN,
        reason=f"insufficient evidence for classification (conclusion={conclusion or 'none'})",
    )
