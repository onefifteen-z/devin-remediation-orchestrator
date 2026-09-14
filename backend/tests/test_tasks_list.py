from app.models.task import TaskKind, TaskStatus, TriggerSource
from app.repositories.tasks import TaskListQuery, TaskRepository
from app.schemas.task import TaskCreate


def _create_task(
    repo: TaskRepository,
    *,
    issue_number: int,
    issue_title: str,
    task_kind: str = TaskKind.REMEDIATION.value,
    issue_type: str = "bug",
    trigger_source: str = TriggerSource.GITHUB_WEBHOOK.value,
    status: TaskStatus = TaskStatus.RECEIVED,
) -> None:
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=f"delivery-{issue_number}",
            github_repository="owner/repo",
            github_issue_number=issue_number,
            github_issue_url=f"https://github.com/owner/repo/issues/{issue_number}",
            issue_title=issue_title,
            issue_type=issue_type,
            task_kind=task_kind,
            trigger_source=trigger_source,
        )
    )
    if status != TaskStatus.RECEIVED:
        repo.update_status(task, status)


def test_list_tasks_excludes_smoke_tests_by_default(db_session):
    repo = TaskRepository(db_session)
    _create_task(repo, issue_number=1, issue_title="Real bug")
    _create_task(
        repo,
        issue_number=2,
        issue_title="Webhook integration smoke test",
        task_kind=TaskKind.SMOKE_TEST.value,
    )

    items, total = repo.list_tasks(TaskListQuery())
    assert total == 1
    assert len(items) == 1
    assert items[0].github_issue_number == 1


def test_list_tasks_includes_dummy_label_smoke_test_when_requested(db_session):
    repo = TaskRepository(db_session)
    _create_task(repo, issue_number=1, issue_title="Prod bug")
    _create_task(
        repo,
        issue_number=2,
        issue_title="Webhook check",
        issue_type="dummy",
    )

    hidden, hidden_total = repo.list_tasks(TaskListQuery())
    assert hidden_total == 1

    visible, visible_total = repo.list_tasks(
        TaskListQuery(include_smoke_tests=True)
    )
    assert visible_total == 2


def test_list_tasks_filters_status_and_search(db_session):
    repo = TaskRepository(db_session)
    _create_task(
        repo,
        issue_number=10,
        issue_title="Helm chart fix",
        status=TaskStatus.MERGED,
    )
    _create_task(repo, issue_number=11, issue_title="MCP backend fix")

    merged, merged_total = repo.list_tasks(
        TaskListQuery(status=TaskStatus.MERGED.value)
    )
    assert merged_total == 1
    assert merged[0].github_issue_number == 10

    helm, helm_total = repo.list_tasks(TaskListQuery(search="helm"))
    assert helm_total == 1
    assert helm[0].issue_title == "Helm chart fix"


def test_list_tasks_pagination_and_sort(db_session):
    repo = TaskRepository(db_session)
    _create_task(repo, issue_number=1, issue_title="First")
    _create_task(repo, issue_number=2, issue_title="Second")
    _create_task(repo, issue_number=3, issue_title="Third")

    page, total = repo.list_tasks(
        TaskListQuery(limit=2, offset=0, sort_by="issue_number", sort_order="asc")
    )
    assert total == 3
    assert [task.github_issue_number for task in page] == [1, 2]

    page_two, _ = repo.list_tasks(
        TaskListQuery(limit=2, offset=2, sort_by="issue_number", sort_order="asc")
    )
    assert [task.github_issue_number for task in page_two] == [3]


def test_list_tasks_api_query_params(client, db_session):
    repo = TaskRepository(db_session)
    _create_task(repo, issue_number=1, issue_title="Prod")
    _create_task(
        repo,
        issue_number=2,
        issue_title="Smoke",
        issue_type="dummy",
    )

    response = client.get("/api/tasks")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1

    response = client.get("/api/tasks?include_smoke_tests=true")
    assert response.status_code == 200
    assert response.json()["total"] == 2

    response = client.get("/api/tasks?sort_by=invalid")
    assert response.status_code == 400
