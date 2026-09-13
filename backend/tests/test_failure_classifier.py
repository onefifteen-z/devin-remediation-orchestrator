from app.schemas.ci import CiCheckRunEvent, FailureType
from app.services.failure_classifier import classify


def _event(
    conclusion: str,
    check_name: str = "Check",
    output_title: str | None = None,
    output_summary: str | None = None,
) -> CiCheckRunEvent:
    return CiCheckRunEvent(
        delivery_id="d1",
        repository="owner/repo",
        action="completed",
        check_run_id=1,
        check_name=check_name,
        status="completed",
        conclusion=conclusion,
        output_title=output_title,
        output_summary=output_summary,
    )


def test_failure_pytest_is_code_failure():
    result = classify(_event("failure", "Python Unit Tests", output_summary="pytest failed"))
    assert result.failure_type == FailureType.CODE_FAILURE


def test_failure_lint_is_code_failure():
    result = classify(_event("failure", "Lint", output_summary="eslint found 3 errors"))
    assert result.failure_type == FailureType.CODE_FAILURE


def test_failure_without_code_signal_is_unknown():
    result = classify(_event("failure", "Deploy Preview", output_summary="Unknown deployment error"))
    assert result.failure_type == FailureType.UNKNOWN


def test_cancelled_is_transient_failure():
    result = classify(_event("cancelled", "Python Unit Tests", output_summary="15138 passed"))
    assert result.failure_type == FailureType.TRANSIENT_FAILURE


def test_timed_out_is_transient_failure():
    result = classify(_event("timed_out", "CI"))
    assert result.failure_type == FailureType.TRANSIENT_FAILURE


def test_stale_is_transient_failure():
    result = classify(_event("stale", "Build"))
    assert result.failure_type == FailureType.TRANSIENT_FAILURE


def test_startup_failure_is_infra_failure():
    result = classify(_event("startup_failure", "Build"))
    assert result.failure_type == FailureType.INFRA_FAILURE


def test_runner_infrastructure_evidence_is_infra_failure():
    result = classify(
        _event("failure", "Build", output_summary="runner unavailable during setup")
    )
    assert result.failure_type == FailureType.INFRA_FAILURE


def test_action_required_is_unknown():
    result = classify(_event("action_required", "Security Scan"))
    assert result.failure_type == FailureType.UNKNOWN


def test_success_conclusion_not_classified_as_failure():
    from app.schemas.ci import FAILURE_LIKE_CONCLUSIONS

    assert "success" not in FAILURE_LIKE_CONCLUSIONS
