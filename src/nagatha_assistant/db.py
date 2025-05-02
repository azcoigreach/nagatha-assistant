import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

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