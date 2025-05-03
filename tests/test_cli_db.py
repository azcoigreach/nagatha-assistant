import os
import sys
import sqlite3
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# Ensure project src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from nagatha_assistant.cli import cli
from nagatha_assistant.db import Base


@pytest.fixture(autouse=True)
def isolate_env(tmp_path, monkeypatch):
    """Isolate environment for each test and set working dir to tmp."""
    monkeypatch.chdir(tmp_path)
    # Clear any existing DATABASE_URL
    monkeypatch.delenv('DATABASE_URL', raising=False)
    yield


def test_db_upgrade_fresh(tmp_path, monkeypatch):
    runner = CliRunner()
    db_file = tmp_path / 'fresh.db'
    # Use a fresh SQLite database path
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_file}')

    result = runner.invoke(cli, ['db', 'upgrade'])
    assert result.exit_code == 0
    assert 'Database successfully upgraded to the latest revision.' in result.output
    # DB file should have been created
    assert db_file.exists()
    # Alembic version table should exist
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
    assert cur.fetchone() is not None
    conn.close()


def test_db_upgrade_existing_schema(tmp_path, monkeypatch):
    runner = CliRunner()
    db_file = tmp_path / 'existing.db'
    # Create DB with tables via metadata (no alembic_version table)
    engine = create_engine(f'sqlite:///{db_file}')
    Base.metadata.create_all(engine)
    engine.dispose()
    # No alembic_version table initially
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
    assert cur.fetchone() is None
    conn.close()

    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_file}')
    result = runner.invoke(cli, ['db', 'upgrade'])
    # Should stamp to head
    assert 'Detected existing schema; stamping database to the latest Alembic revision.' in result.output
    assert 'Database marked as up-to-date (stamped to head).' in result.output
    # Alembic version table should now exist
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
    assert cur.fetchone() is not None
    conn.close()


@pytest.mark.parametrize('url, expected_msg', [
    ('postgresql://user@host/db', 'Backup is only supported for SQLite databases.'),
    ('sqlite:///:memory:', 'Cannot backup in-memory or invalid SQLite database.'),
    ('sqlite:///nonexistent.db', 'SQLite database file not found'),
])
def test_db_backup_errors(tmp_path, monkeypatch, url, expected_msg):
    runner = CliRunner()
    monkeypatch.setenv('DATABASE_URL', url)
    result = runner.invoke(cli, ['db', 'backup'])
    assert expected_msg in result.output


def test_db_backup_with_destination(tmp_path, monkeypatch):
    runner = CliRunner()
    # Create a dummy database file
    src = tmp_path / 'srcfile.db'
    src.write_bytes(b'hello world')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{src}')
    dest = tmp_path / 'destfile.db'
    result = runner.invoke(cli, ['db', 'backup', str(dest)])
    assert result.exit_code == 0
    assert f'Database backed up to {dest}' in result.output
    # Content should match
    assert dest.exists()
    assert dest.read_bytes() == b'hello world'


def test_db_backup_default_timestamp(tmp_path, monkeypatch):
    runner = CliRunner()
    # Create a dummy database file
    src = tmp_path / 'srcfile.db'
    src.write_bytes(b'data')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{src}')
    # Freeze datetime in CLI to fixed timestamp
    import importlib
    import datetime as _dt

    class DummyDateTime(_dt.datetime):
        @classmethod
        def now(cls):
            return cls(2020, 1, 1, 0, 0, 0)

    import nagatha_assistant.cli as cli_mod
    monkeypatch.setattr(cli_mod, 'datetime', DummyDateTime)

    result = runner.invoke(cli, ['db', 'backup'])
    assert result.exit_code == 0
    # Expect filename with frozen timestamp
    expected_name = 'srcfile_backup_20200101T000000.db'
    dest = src.with_name(expected_name)
    assert dest.exists()
    assert dest.read_bytes() == b'data'