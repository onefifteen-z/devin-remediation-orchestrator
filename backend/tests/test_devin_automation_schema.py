from app.schemas.devin_automation import (
    build_scheduled_intake_automation_body,
    cron_to_rrule,
    parse_automation_response,
)


def test_cron_to_rrule_daily():
    assert cron_to_rrule("0 0 * * *") == "FREQ=DAILY;BYHOUR=0;BYMINUTE=0"


def test_cron_to_rrule_weekdays():
    assert (
        cron_to_rrule("0 9 * * 1-5")
        == "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9;BYMINUTE=0"
    )


def test_build_scheduled_intake_automation_body():
    body = build_scheduled_intake_automation_body(
        name="Remediation intake triage",
        prompt="scan issues",
        cron="0 0 * * *",
        playbook_id="playbook-001",
    )
    assert body["name"] == "Remediation intake triage"
    assert body["run_as"] == {"type": "organization"}
    assert body["triggers"][0]["event_type"] == "schedule:recurring"
    assert body["actions"][0]["type"] == "start_session"
    assert body["actions"][0]["prompt"].startswith("@playbook:playbook-001")
    assert body["metadata"]["workflow"] == "scheduled-intake"


def test_parse_automation_response():
    automation = parse_automation_response(
        {
            "automation_id": "auto-abc123",
            "name": "Remediation intake triage",
            "enabled": True,
        }
    )
    assert automation.automation_id == "auto-abc123"
