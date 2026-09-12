from app.models.task import RemediationTask


def build_remediation_prompt(task: RemediationTask) -> str:
    return f"""You are responsible for remediating the following engineering issue.

Repository:
{task.github_repository}

Issue:
{task.github_issue_url}

Title:
{task.issue_title}

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
"""


def build_session_tags(task: RemediationTask) -> list[str]:
    return [
        "source=github",
        "workflow=issue-remediation",
        f"repo={task.github_repository}",
        f"issue={task.github_issue_number}",
        f"issue-type={task.issue_type}",
        "environment=take-home",
    ]
