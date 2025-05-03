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

# ---------------------------------------------------------------------------
# Alembic helper – ensure DB schema is up-to-date
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _migration_runner() -> None:
    """Run Alembic migrations to *head* (idempotent)."""

    try:
        from alembic.config import Config  # type: ignore
        from alembic import command  # type: ignore

        # Repo root two levels up from this file: src/nagatha_assistant/db.py -> src -> repo
        root = pathlib.Path(__file__).resolve().parents[2]
        cfg_path = str(root / "alembic.ini")
        cfg = Config(cfg_path)

        # Ensure absolute script location – avoids relative-path issues when
        # running from different cwd (e.g. pytest)
        script_loc = str(root / "migrations")
        cfg.set_main_option("script_location", script_loc)

        # Override DB URL
        cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

        try:
            command.upgrade(cfg, "head")
        except Exception as exc:  # noqa: BLE001
            # If tables already exist (e.g. tests ran concurrently), ignore.
            if "already exists" in str(exc):
                logging.getLogger(__name__).debug("Schema already present, skip")
            else:
                raise
    except ModuleNotFoundError:
        # Alembic not installed in minimal environments (e.g. CI tests). Fall
        # back to metadata.create_all as before.
        import nagatha_assistant.db_models  # noqa: F401

        logging.getLogger(__name__).warning(
            "Alembic not installed – falling back to Base.metadata.create_all().",
        )
        import sqlalchemy as sa

        sync_engine = sa.create_engine(DATABASE_URL.replace("+aiosqlite", ""))
        nagatha_assistant.db_models.Base.metadata.create_all(sync_engine)


async def ensure_schema() -> None:
    # Serialise access so migrations are only run once even if multiple
    # coroutines hit this function concurrently (e.g. pytest workers).
    loop = asyncio.get_running_loop()

    def runner():  # noqa: D401
        with _LOCK:
            _migration_runner()

    await loop.run_in_executor(None, runner)