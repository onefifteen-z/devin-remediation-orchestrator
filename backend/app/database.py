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
            if (
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
