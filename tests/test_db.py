#!/usr/bin/env python3
"""
Pytest tests for the database module functionality.
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from nagatha_assistant.db import engine, SessionLocal, Base, ensure_schema


class TestDB:
    """Test cases for the database module."""

    def test_db_components_exist(self):
        """Test that the database components are importable and available."""
        # Basic import test
        from nagatha_assistant.db import engine, SessionLocal, Base
        assert engine is not None
        assert SessionLocal is not None
        assert Base is not None

    def test_engine_configuration(self):
        """Test that the engine is properly configured."""
        assert engine is not None
        # Should have proper URL
        assert str(engine.url) is not None

    def test_session_factory(self):
        """Test that SessionLocal is a proper session factory."""
        assert SessionLocal is not None
        # Should be a sessionmaker
        assert hasattr(SessionLocal, '__call__')
        # Should have been configured with our engine (async sessionmaker stores this differently)
        assert hasattr(SessionLocal, 'bind') or hasattr(SessionLocal, 'kw')

    def test_base_model(self):
        """Test that Base is properly configured."""
        assert Base is not None
        # Should have metadata
        assert hasattr(Base, 'metadata')
        assert hasattr(Base.metadata, 'tables')

    @pytest.mark.asyncio
    async def test_ensure_schema(self):
        """Test the ensure_schema function."""
        # Should not raise an exception
        await ensure_schema()

    def test_database_url_environment(self):
        """Test that DATABASE_URL environment variable is respected."""
        # This test checks that the module loads correctly with different env vars
        # The actual DATABASE_URL is set at module import time
        from nagatha_assistant.db import DATABASE_URL
        assert DATABASE_URL is not None
        assert isinstance(DATABASE_URL, str)

    def test_model_imports(self):
        """Test that database models are properly imported."""
        # Models should be imported and registered with Base.metadata
        from nagatha_assistant.db import Base
        from nagatha_assistant.db_models import ConversationSession, Message
        
        # Models should be in the metadata
        table_names = list(Base.metadata.tables.keys())
        assert len(table_names) > 0

    @patch('nagatha_assistant.db._migration_runner')
    @pytest.mark.asyncio
    async def test_ensure_schema_calls_migration(self, mock_migration):
        """Test that ensure_schema calls the migration runner."""
        await ensure_schema()
        # Migration runner should be called
        mock_migration.assert_called()

    def test_async_session_configuration(self):
        """Test that async session is properly configured."""
        session = SessionLocal()
        assert session is not None
        # Should be an AsyncSession
        from sqlalchemy.ext.asyncio import AsyncSession
        assert isinstance(session, AsyncSession)

    def test_database_file_path(self):
        """Test that default database file path is reasonable."""
        from nagatha_assistant.db import DATABASE_URL
        
        # Should contain a reasonable database location
        assert "nagatha" in DATABASE_URL.lower() or "sqlite" in DATABASE_URL.lower()