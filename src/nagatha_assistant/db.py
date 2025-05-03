import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from functools import lru_cache
import concurrent.futures, asyncio, logging, pathlib, threading


# Load environment variables
load_dotenv()
# Database URL, defaulting to local SQLite file
# Ensure use of async driver for SQLite
raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nagatha.db")
if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite+aiosqlite:///"):
    DATABASE_URL = raw_url.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    DATABASE_URL = raw_url

# Create an async engine
engine = create_async_engine(
    DATABASE_URL, echo=(os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG")
)

# Async session factory
SessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# Import models so they are registered with Base.metadata
import nagatha_assistant.db_models  # noqa: F401

# Lock to ensure Alembic migrations are executed only once at a time
_LOCK = threading.Lock()

## ---------------------------------------------------------------------------
# Alembic helper – ensure DB schema is up-to-date
## ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _migration_runner() -> None:
    """Run Alembic migrations to *head* (idempotent), then create any missing tables."""

    # If using a SQLite file-based DB and the file already exists, skip migrations (assume schema is managed externally)
    if DATABASE_URL.startswith("sqlite") and ":memory:" not in DATABASE_URL:
        # Extract file path after '///'
        parts = DATABASE_URL.split("///", 1)
        if len(parts) == 2:
            db_file = parts[1]
            try:
                import os as _os
                if _os.path.exists(db_file):
                    return
            except Exception:
                pass
    # Attempt Alembic migrations
    try:
        from alembic.config import Config  # type: ignore
        from alembic import command  # type: ignore

        root = pathlib.Path(__file__).resolve().parents[2]
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "migrations"))
        cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        try:
            command.upgrade(cfg, "head")
        except Exception as exc:  # noqa: BLE001
            if "already exists" in str(exc):
                logging.getLogger().debug("Schema already present, skip Alembic upgrade")
            else:
                raise
    except ModuleNotFoundError:
        logging.getLogger().warning(
            "Alembic not installed – falling back to metadata.create_all()"
        )

    # Ensure any missing tables are created via metadata
    try:
        import sqlalchemy as sa
        from nagatha_assistant.db_models import Base as _Base  # type: ignore

        sync_url = DATABASE_URL.replace("+aiosqlite", "")
        sync_engine = sa.create_engine(sync_url)
        _Base.metadata.create_all(sync_engine)
    except Exception:
        pass


async def ensure_schema() -> None:
    # Serialise access so migrations are only run once even if multiple
    # coroutines hit this function concurrently (e.g. pytest workers).
    loop = asyncio.get_running_loop()

    def runner():  # noqa: D401
        with _LOCK:
            _migration_runner()

    # Run migrations/thread-safe operations
    await loop.run_in_executor(None, runner)
    # Ensure all tables (including new models) exist via metadata.create_all
    try:
        import sqlalchemy as sa
        from nagatha_assistant.db_models import Base as _Base
        # Use synchronous engine for DDL
        sync_url = DATABASE_URL.replace("+aiosqlite", "")
        sync_engine = sa.create_engine(sync_url)
        _Base.metadata.create_all(sync_engine)
    except Exception:
        pass