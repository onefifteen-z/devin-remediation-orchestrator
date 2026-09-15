from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _ensure_data_dir(database_url: str) -> None:
    if database_url.startswith("sqlite:///./"):
        data_dir = Path(database_url.replace("sqlite:///./", "").rsplit("/", 1)[0])
        data_dir.mkdir(parents=True, exist_ok=True)


_engine = None
_SessionLocal = None

PHASE_2B_AUDIT_COLUMNS = {
    "pr_state",
    "devin_status",
    "devin_status_detail",
    "devin_origin",
    "devin_service_user_id",
    "devin_tags",
}

PHASE_2C_COLUMNS = {"merge_notification_sent"}

PHASE_3_CI_COLUMNS = {
    "failure_type",
    "ci_classification_reason",
    "ci_check_name",
    "ci_check_url",
    "ci_conclusion",
    "ci_failure_at",
    "ci_repair_attempts",
    "last_ci_check_run_id",
    "ci_repair_message_sent_at",
    "ci_repair_verified_at",
    "ci_non_code_failure_count",
}

PHASE_5_TRIGGER_SOURCE_COLUMNS = {"trigger_source"}

PHASE_5_ADVANCED_COLUMNS = {
    "remediation_outcome",
    "root_cause",
    "implementation_summary",
    "structured_result_json",
    "blocker",
    "playbook_id",
    "acu_source",
    "acu_verified",
}

PHASE_7_TASK_KIND_COLUMNS = {"task_kind"}

PHASE_8_SESSION_INSIGHTS_COLUMNS = {
    "session_size",
    "num_user_messages",
    "num_devin_messages",
    "insights_status",
    "insights_json",
}

PHASE_9_ISSUE_LABELS_COLUMNS = {"issue_labels"}

PHASE_10_COMPLETION_COLUMNS = {"ci_passed_at", "completion_reason"}


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _ensure_data_dir(settings.database_url)
        _engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False}
            if settings.database_url.startswith("sqlite")
            else {},
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def _upgrade_database(engine, database_url: str) -> None:
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext

    backend_root = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        current_revision = MigrationContext.configure(connection).get_current_revision()
        inspector = inspect(connection)
        has_legacy_table = inspector.has_table("remediation_tasks")

        if current_revision is None and has_legacy_table:
            columns = {
                column["name"]
                for column in inspector.get_columns("remediation_tasks")
            }
            unique_constraints = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("remediation_tasks")
            }
            has_webhook_deliveries = inspector.has_table("github_webhook_deliveries")
            has_phase_2b = (
                PHASE_2B_AUDIT_COLUMNS.issubset(columns)
                and "uq_repo_issue" in unique_constraints
            )
            has_phase_3_ci = PHASE_3_CI_COLUMNS.issubset(columns)
            has_trigger_source = PHASE_5_TRIGGER_SOURCE_COLUMNS.issubset(columns)
            has_phase_5_advanced = PHASE_5_ADVANCED_COLUMNS.issubset(columns)
            has_phase_7_task_kind = PHASE_7_TASK_KIND_COLUMNS.issubset(columns)
            has_phase_8_session_insights = PHASE_8_SESSION_INSIGHTS_COLUMNS.issubset(columns)
            has_phase_9_issue_labels = PHASE_9_ISSUE_LABELS_COLUMNS.issubset(columns)
            has_phase_10_completion = PHASE_10_COMPLETION_COLUMNS.issubset(columns)
            if (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
                and has_phase_5_advanced
                and has_phase_7_task_kind
                and has_phase_8_session_insights
                and has_phase_9_issue_labels
                and has_phase_10_completion
            ):
                baseline = "0010"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
                and has_phase_5_advanced
                and has_phase_7_task_kind
                and has_phase_8_session_insights
                and has_phase_9_issue_labels
            ):
                baseline = "0009"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
                and has_phase_5_advanced
                and has_phase_7_task_kind
                and has_phase_8_session_insights
            ):
                baseline = "0008"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
                and has_phase_5_advanced
                and has_phase_7_task_kind
            ):
                baseline = "0007"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
                and has_phase_5_advanced
            ):
                baseline = "0006"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
                and has_trigger_source
            ):
                baseline = "0005"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
                and has_phase_3_ci
            ):
                baseline = "0004"
            elif (
                has_phase_2b
                and PHASE_2C_COLUMNS.issubset(columns)
                and has_webhook_deliveries
            ):
                baseline = "0003"
            elif has_phase_2b:
                baseline = "0002"
            else:
                baseline = "0001"
            command.stamp(alembic_cfg, baseline)

        command.upgrade(alembic_cfg, "head")


def run_migrations() -> None:
    settings = get_settings()
    _ensure_data_dir(settings.database_url)
    _upgrade_database(get_engine(), settings.database_url)


def init_db() -> None:
    run_migrations()


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def reset_database(database_url: str) -> None:
    """Test helper to rebind the database engine."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_kwargs: dict = {"connect_args": connect_args}
    if database_url in {"sqlite:///:memory:", "sqlite://"}:
        from sqlalchemy.pool import StaticPool

        engine_kwargs["poolclass"] = StaticPool
    _engine = create_engine(database_url, **engine_kwargs)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
