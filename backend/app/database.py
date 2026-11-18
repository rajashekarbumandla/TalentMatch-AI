"""
Database layer: SQLAlchemy engine and sessions for Supabase PostgreSQL.

How it fits together:
    engine        -> a pool of connections to Supabase (created once at import time)
    SessionLocal  -> makes a Session (one unit of work / transaction) per request
    get_db()      -> FastAPI dependency: opens a session, rolls back on error, always closes it
    init_db()     -> creates missing tables and enables Row Level Security

The connection URL comes only from the DATABASE_URL environment variable
(backend/.env). It must use the Supabase *Session pooler* (port 5432).
"""
import logging
from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Predictable constraint/index names (e.g. "fk_match_results_job_id_jobs") make
# database errors easier to read and keep the schema tidy.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _mask_password(message: str) -> str:
    """Remove the database password from an error message before it is logged or returned."""
    try:
        password = make_url(settings.DATABASE_URL).password
    except Exception:
        password = None
    return message.replace(password, "****") if password else message


def describe_db_error(exc: Exception) -> str:
    """Short, credential-free description of a database error (first line only)."""
    first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return _mask_password(first_line)


def _build_engine() -> tuple[Engine | None, str | None]:
    """Create the engine, or return (None, reason) when the URL is missing/invalid."""
    if not settings.DATABASE_URL:
        return None, "DATABASE_URL is not set in backend/.env."
    try:
        url = make_url(settings.DATABASE_URL)
    except ArgumentError:
        return None, "DATABASE_URL is not a valid URL. Expected postgresql+psycopg://user:password@host:5432/postgres"
    if url.drivername != "postgresql+psycopg":
        return None, f"DATABASE_URL must start with 'postgresql+psycopg://' (found '{url.drivername}://')."

    new_engine = create_engine(
        url,
        pool_pre_ping=True,   # test each pooled connection before use (Supabase closes idle ones)
        pool_size=settings.DB_POOL_SIZE,  # the free Supabase pooler allows only a limited number of clients
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=1800,    # replace connections older than 30 minutes
        connect_args={"connect_timeout": 10},
    )
    return new_engine, None


engine, DB_CONFIG_ERROR = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def check_database_connection() -> tuple[bool, str]:
    """Run `SELECT 1`. Returns (connected, human-readable message)."""
    if engine is None:
        return False, DB_CONFIG_ERROR or "Database is not configured."
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "Connected to Supabase PostgreSQL."
    except Exception as exc:
        return False, f"Cannot connect to the database: {describe_db_error(exc)}"


def init_db() -> list[str]:
    """
    Create any missing tables (existing tables and data are left untouched) and
    enable Row Level Security on each one. Returns the table names.

    Why RLS: Supabase automatically exposes tables in the `public` schema through
    its REST API. With RLS enabled and no policies, that API cannot read or write
    them, while this backend (connected as the table owner) keeps full access.
    """
    if engine is None:
        raise RuntimeError(DB_CONFIG_ERROR or "Database is not configured.")
    from app import models  # noqa: F401  (importing registers the tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    table_names = list(Base.metadata.tables)
    with engine.begin() as connection:
        # create_all() only creates MISSING tables; columns added later to existing tables
        # are added here. Every statement is idempotent ("IF NOT EXISTS"), so this is safe to rerun.
        for statement in SCHEMA_MIGRATIONS:
            connection.execute(text(statement))
        for table_name in table_names:
            connection.execute(text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
    return table_names


# Small, explicit migrations for databases created before a column existed.
SCHEMA_MIGRATIONS = [
    # HR accounts: each job/candidate belongs to the HR who created it.
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE CASCADE",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE CASCADE",
    "CREATE INDEX IF NOT EXISTS ix_jobs_owner_id ON jobs (owner_id)",
    "CREATE INDEX IF NOT EXISTS ix_candidates_owner_id ON candidates (owner_id)",
]


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides one database session per request.
    Any exception rolls back the open transaction so no half-written data is kept.
    """
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {DB_CONFIG_ERROR}",
        )
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
