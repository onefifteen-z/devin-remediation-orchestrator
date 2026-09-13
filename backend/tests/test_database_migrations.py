from sqlalchemy import create_engine, inspect, text

from app.database import Base, _upgrade_database
from app.models.task import RemediationTask  # noqa: F401
from app.models.webhook_delivery import WebhookDelivery  # noqa: F401


LEGACY_SCHEMA = """
CREATE TABLE remediation_tasks (
    id INTEGER NOT NULL PRIMARY KEY,
    github_delivery_id VARCHAR(64) NOT NULL,
    github_repository VARCHAR(255) NOT NULL,
    github_issue_number INTEGER NOT NULL,
    github_issue_url VARCHAR(512) NOT NULL,
    issue_title VARCHAR(512) NOT NULL,
    issue_type VARCHAR(64) NOT NULL,
    devin_session_id VARCHAR(128),
    devin_session_url VARCHAR(512),
    status VARCHAR(16) NOT NULL,
    pr_url VARCHAR(512),
    retry_count INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    started_at DATETIME,
    completed_at DATETIME,
    merged_at DATETIME,
    failure_reason TEXT,
    escalation_reason TEXT,
    acu_used FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
)
"""


def test_upgrade_database_bootstraps_new_database(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'new.db'}"
    engine = create_engine(database_url)

    _upgrade_database(engine, database_url)

    inspector = inspect(engine)
    assert inspector.has_table("remediation_tasks")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"


def test_upgrade_database_stamps_and_migrates_legacy_database(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(LEGACY_SCHEMA))

    _upgrade_database(engine, database_url)

    columns = {column["name"] for column in inspect(engine).get_columns("remediation_tasks")}
    assert {
        "pr_state",
        "devin_status",
        "devin_status_detail",
        "devin_origin",
        "devin_service_user_id",
        "devin_tags",
        "merge_notification_sent",
        "failure_type",
        "ci_classification_reason",
        "ci_check_name",
        "ci_repair_attempts",
        "trigger_source",
    }.issubset(columns)
    assert inspect(engine).has_table("github_webhook_deliveries")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"


def test_upgrade_database_stamps_unversioned_current_schema_at_head(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'current.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    _upgrade_database(engine, database_url)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"
