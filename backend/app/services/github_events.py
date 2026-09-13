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


def find_task_for_check_run(
    repo: TaskRepository,
    repository: str,
    pr_numbers: list[int],
) -> RemediationTask | None:
    """Deterministically associate a check_run with a remediation task via PR number."""
    if not pr_numbers:
        return None
    pr_number = pr_numbers[0]
    pr_url = f"https://github.com/{repository}/pull/{pr_number}"
    return find_task_for_pr(repo, repository, pr_url, pr_number)
