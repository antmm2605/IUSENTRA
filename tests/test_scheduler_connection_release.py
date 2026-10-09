"""Il registro non deve conservare file e lock dopo una transazione breve."""

import sqlite3

import pytest

from pct.scheduler_registry import SchedulerRegistryRepository
from pct.sqlite_connection import ClosingSQLiteConnection


def test_registry_context_commits_and_closes(tmp_path):
    repo = SchedulerRegistryRepository(tmp_path / 'scheduler.sqlite')
    with repo.connect() as conn:
        conn.execute('CREATE TABLE release_probe (value TEXT)')
        conn.execute('INSERT INTO release_probe VALUES (?)', ('confermato',))
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        conn.execute('SELECT 1')
    with repo.connect() as check:
        assert check.execute('SELECT value FROM release_probe').fetchone()[0] == 'confermato'


def test_registry_context_rolls_back_and_closes(tmp_path):
    repo = SchedulerRegistryRepository(tmp_path / 'scheduler.sqlite')
    with repo.connect() as schema:
        schema.execute('CREATE TABLE release_probe (value TEXT)')
    with pytest.raises(ValueError, match='interrotto'):
        with repo.connect() as conn:
            conn.execute('INSERT INTO release_probe VALUES (?)', ('da annullare',))
            raise ValueError('interrotto')
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        conn.execute('SELECT 1')
    with repo.connect() as check:
        assert check.execute('SELECT COUNT(*) FROM release_probe').fetchone()[0] == 0


def test_registry_failed_connection_setup_releases_file(tmp_path, monkeypatch):
    repo = SchedulerRegistryRepository(tmp_path / 'scheduler.sqlite')
    original_connect = sqlite3.connect
    opened = []

    class JournalUnavailable(ClosingSQLiteConnection):
        def execute(self, sql, *args):
            if sql == 'PRAGMA journal_mode=WAL':
                raise sqlite3.OperationalError('database is locked')
            return super().execute(sql, *args)

    def failing_connect(*args, **kwargs):
        kwargs['factory'] = JournalUnavailable
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', failing_connect)
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        repo.connect()
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        opened[0].execute('SELECT 1')
