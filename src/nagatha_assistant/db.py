import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Database URL, defaulting to local SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///nagatha.db")

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