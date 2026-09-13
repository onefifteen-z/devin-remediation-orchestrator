from app.schemas.devin_schedule import (
    build_schedule_create_body,
    parse_schedule_response,
)


def test_build_schedule_create_body_uses_name_not_title():
    body = build_schedule_create_body(
        name="Remediation intake triage",
        prompt="scan issues",
        frequency="0 0 * * *",
        tags=["workflow=scheduled-intake"],
        playbook_id="playbook-001",
    )
    assert body["name"] == "Remediation intake triage"
    assert "title" not in body
    assert body["prompt"] == "scan issues"
    assert body["frequency"] == "0 0 * * *"
    assert body["playbook_id"] == "playbook-001"


def test_parse_schedule_response_accepts_scheduled_session_id():
    schedule = parse_schedule_response(
        {
            "scheduled_session_id": "sched-abc123",
            "name": "Remediation intake triage",
            "prompt": "scan",
            "schedule_type": "recurring",
            "frequency": "0 0 * * *",
            "enabled": True,
            "org_id": "org-test",
            "created_by": "user-1",
            "playbook": {"playbook_id": "pb-1", "title": "Remediation"},
            "last_executed_at": None,
            "created_at": "2026-03-13T00:00:00Z",
            "updated_at": "2026-03-13T00:00:00Z",
            "last_error_at": None,
            "last_error_message": None,
            "consecutive_failures": 0,
            "notify_on": "failure",
            "agent": "devin",
        }
    )
    assert schedule.schedule_id == "sched-abc123"
    assert schedule.name == "Remediation intake triage"
    assert schedule.playbook is not None
    assert schedule.playbook.playbook_id == "pb-1"


def test_parse_schedule_response_accepts_legacy_schedule_id():
    schedule = parse_schedule_response(
        {
            "schedule_id": "sched-legacy",
            "name": "Legacy",
            "prompt": "scan",
        }
    )
    assert schedule.schedule_id == "sched-legacy"
