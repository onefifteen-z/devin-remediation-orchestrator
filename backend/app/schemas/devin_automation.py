from typing import Any

from pydantic import BaseModel, ConfigDict, Field

AUTOMATION_METADATA_WORKFLOW = "scheduled-intake"
AUTOMATION_METADATA_ENVIRONMENT = "take-home"

_CRON_DOW_TO_RRULE = ("SU", "MO", "TU", "WE", "TH", "FR", "SA")


class AutomationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    automation_id: str
    name: str | None = None
    enabled: bool | None = None


def cron_to_rrule(cron: str) -> str:
    """Convert a 5-field cron expression to an iCalendar RRULE for schedule:recurring."""
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got: {cron}")

    minute, hour, day_of_month, month, day_of_week = parts
    if minute == "*" or hour == "*" or day_of_month != "*" or month != "*":
        raise ValueError(f"Unsupported cron expression for automation schedule: {cron}")

    byminute = int(minute)
    byhour = int(hour)
    if day_of_week == "*":
        return f"FREQ=DAILY;BYHOUR={byhour};BYMINUTE={byminute}"

    bydays = _expand_cron_days(day_of_week)
    return f"FREQ=WEEKLY;BYDAY={','.join(bydays)};BYHOUR={byhour};BYMINUTE={byminute}"


def _expand_cron_days(day_of_week: str) -> list[str]:
    days: list[str] = []
    for part in day_of_week.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start_idx = int(start)
            end_idx = int(end)
            if start_idx <= end_idx:
                indices = range(start_idx, end_idx + 1)
            else:
                indices = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
            for idx in indices:
                days.append(_CRON_DOW_TO_RRULE[idx % 7])
        else:
            days.append(_CRON_DOW_TO_RRULE[int(part) % 7])
    return days


def build_automation_prompt(prompt: str, playbook_id: str | None = None) -> str:
    if playbook_id:
        return f"@playbook:{playbook_id}\n\n{prompt}"
    return prompt


def build_scheduled_intake_automation_body(
    *,
    name: str,
    prompt: str,
    cron: str,
    playbook_id: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "enabled": enabled,
        "run_as": {"type": "organization"},
        "metadata": {
            "workflow": AUTOMATION_METADATA_WORKFLOW,
            "environment": AUTOMATION_METADATA_ENVIRONMENT,
        },
        "triggers": [
            {
                "event_type": "schedule:recurring",
                "conditions": {
                    "any": [
                        {
                            "all": [
                                {
                                    "field": "rrule",
                                    "operator": "recurrence",
                                    "value": cron_to_rrule(cron),
                                }
                            ]
                        }
                    ]
                },
            }
        ],
        "actions": [
            {
                "type": "start_session",
                "prompt": build_automation_prompt(prompt, playbook_id),
            }
        ],
    }


def parse_automation_response(data: dict[str, Any]) -> AutomationResponse:
    automation_id = data.get("automation_id")
    if not automation_id:
        raise ValueError("Missing automation_id")
    return AutomationResponse(
        automation_id=str(automation_id),
        name=data.get("name"),
        enabled=data.get("enabled"),
    )


def parse_automation_list_response(data: dict[str, Any]) -> list[AutomationResponse]:
    items = data.get("items") or []
    automations: list[AutomationResponse] = []
    for item in items:
        if isinstance(item, dict):
            automations.append(parse_automation_response(item))
    return automations
