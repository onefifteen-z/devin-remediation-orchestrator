from app.config import Settings
from app.models.task import RemediationTask, TriggerSource


def _trigger_source_tag(task: RemediationTask) -> str:
    source_map = {
        TriggerSource.GITHUB_WEBHOOK.value: "github",
        TriggerSource.MANUAL_API.value: "api",
        TriggerSource.SCAN.value: "scan",
        TriggerSource.SCHEDULED.value: "scheduled",
    }
    return source_map.get(task.trigger_source or "", "unknown")


def build_session_tags(task: RemediationTask) -> list[str]:
    return [
        "workflow=issue-remediation",
        f"source={_trigger_source_tag(task)}",
        f"repo={task.github_repository}",
        f"issue={task.github_issue_number}",
        f"issue-type={task.issue_type}",
        "environment=take-home",
    ]


def build_remediation_prompt(task: RemediationTask, settings: Settings | None = None) -> str:
    issue_body_section = ""
    if task.issue_title and task.issue_title != f"Issue #{task.github_issue_number}":
        pass
    constraints = """Orchestration constraints:
- Update an existing pull request if one already exists for this issue.
- Do not merge pull requests.
- Return structured output with your engineering result."""

    if settings and settings.devin_remediation_playbook_id:
        return f"""Remediate the following engineering issue using the configured remediation playbook.

Repository:
{task.github_repository}

Issue:
{task.github_issue_url}

Title:
{task.issue_title}

Issue type:
{task.issue_type}

{constraints}
"""

    return f"""You are responsible for remediating the following engineering issue.

Repository:
{task.github_repository}

Issue:
{task.github_issue_url}

Title:
{task.issue_title}

Issue type:
{task.issue_type}

Objectives:

1. Understand and reproduce the problem where practical.
2. Diagnose the root cause.
3. Implement the smallest safe fix.
4. Add or update regression tests.
5. Run relevant tests.
6. Check for regressions in affected behavior.
7. Create or update a pull request.
8. Clearly report:
   - root cause
   - implementation
   - tests performed
   - residual risks or limitations

Work autonomously.

Do not stop after analysis unless blocked.

If blocked, clearly report the blocker rather than guessing.

{constraints}
"""
