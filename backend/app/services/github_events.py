from app.models.task import RemediationTask
from app.repositories.tasks import TaskRepository


def find_task_for_pr(
    repo: TaskRepository,
    repository: str,
    pr_url: str,
    pr_number: int,
) -> RemediationTask | None:
    """Deterministically associate a GitHub PR event with a remediation task."""
    exact_match = repo.get_by_pr_url(pr_url)
    if exact_match:
        return exact_match

    by_number = repo.get_by_repository_and_pr_number(repository, pr_number)
    if by_number:
        return by_number

    return None
