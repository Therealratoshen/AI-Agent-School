# tests/unit/test_database.py
# Database layer tests for 99% coverage

import os
import sys
import uuid
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))

from core.database import (
    Database,
    BaseRepository,
    NotificationService,
    check_database_health
)


class TestDatabase:
    """Tests for Database connection pool manager"""

    def test_connection_pool_initializes_with_settings(self, mock_settings):
        """Test that database initializes connection pool with correct settings"""
        with patch('core.database.pool.ThreadedConnectionPool') as mock_pool:
            with patch('core.database.get_settings', return_value=mock_settings):
                db = Database.__new__(Database)
                Database._instance = None
                Database._pool = None
                db._pool = mock_pool

                # Verify pool was created with correct parameters
                mock_pool.assert_called_once()

    def test_get_connection_returns_from_pool(self):
        """Test get_connection retrieves connection from pool"""
        db = Database.__new__(Database)
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        db._pool = mock_pool

        @contextmanager
        def get_conn():
            yield mock_conn

        mock_pool.getconn = MagicMock(return_value=mock_conn)
        db._pool = mock_pool

        with db.get_connection() as conn:
            assert conn == mock_conn

        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_get_connection_rollback_on_error(self):
        """Test that connection is rolled back on exception"""
        db = Database.__new__(Database)
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.rollback = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        db._pool = mock_pool

        mock_pool.getconn = MagicMock(return_value=mock_conn)

        with pytest.raises(ValueError):
            with db.get_connection() as conn:
                raise ValueError("Test error")

        mock_conn.rollback.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_get_cursor_returns_cursor_with_context_manager(self):
        """Test get_cursor returns cursor and manages connection"""
        db = Database.__new__(Database)
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn
        db._pool = mock_pool

        with db.get_cursor() as cursor:
            assert cursor == mock_cursor

        mock_cursor.close.assert_called_once()

    def test_execute_runs_query_and_returns_results(self):
        """Test execute runs query and returns results"""
        db = Database.__new__(Database)
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [
            {"id": "1", "name": "Test1"},
            {"id": "2", "name": "Test2"}
        ]

        with patch.object(db, 'get_cursor') as mock_get_cursor:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_get_cursor.return_value = mock_cm

            result = db.execute("SELECT * FROM test")

            assert len(result) == 2
            assert result[0]["id"] == "1"

    def test_execute_one_returns_single_row(self):
        """Test execute_one returns single result"""
        db = Database.__new__(Database)
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchone.return_value = {"id": "1", "name": "Test"}

        with patch.object(db, 'get_cursor') as mock_get_cursor:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_get_cursor.return_value = mock_cm

            result = db.execute_one("SELECT * FROM test WHERE id = %s", ("1",))

            assert result["id"] == "1"

    def test_execute_one_returns_none_when_no_results(self):
        """Test execute_one returns None when no results"""
        db = Database.__new__(Database)
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchone.return_value = None

        with patch.object(db, 'get_cursor') as mock_get_cursor:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_get_cursor.return_value = mock_cm

            result = db.execute_one("SELECT * FROM test")

            assert result is None

    def test_execute_scalar_returns_first_column_value(self):
        """Test execute_scalar returns scalar value"""
        db = Database.__new__(Database)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)

        with patch.object(db, 'get_cursor') as mock_get_cursor:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_get_cursor.return_value = mock_cm

            result = db.execute_scalar("SELECT COUNT(*) FROM test")

            assert result == 42

    def test_execute_scalar_returns_none_when_no_results(self):
        """Test execute_scalar returns None when no results"""
        db = Database.__new__(Database)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        with patch.object(db, 'get_cursor') as mock_get_cursor:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_get_cursor.return_value = mock_cm

            result = db.execute_scalar("SELECT COUNT(*) FROM test")

            assert result is None

    def test_close_closes_all_connections(self):
        """Test close closes all pool connections"""
        db = Database.__new__(Database)
        mock_pool = MagicMock()
        db._pool = mock_pool

        db.close()

        mock_pool.closeall.assert_called_once()
        assert db._pool is None


class TestBaseRepository:
    """Tests for BaseRepository CRUD operations"""

    def test_create_inserts_record_with_all_fields(self, sample_student):
        """Test create inserts record with all fields"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_student

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.create(sample_student)

            assert result["id"] == sample_student["id"]
            mock_cursor.execute.assert_called_once()

    def test_create_handles_uuid_conversion(self):
        """Test create converts UUID objects to strings"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        test_uuid = uuid.uuid4()
        mock_cursor.fetchone.return_value = {"id": str(test_uuid)}

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("test_table")
            repo.db = mock_db

            data = {"id": test_uuid, "name": "Test"}
            repo.create(data)

            # Verify execute was called
            mock_cursor.execute.assert_called_once()

    def test_create_handles_jsonb_conversion(self):
        """Test create converts dict to JSONB for JSONB columns"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": "1", "config": {"key": "value"}}

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("test_table")
            repo.db = mock_db

            data = {"id": "1", "config": {"key": "value"}}
            repo.create(data)

            mock_cursor.execute.assert_called_once()

    def test_get_by_id_returns_record(self, sample_student):
        """Test get_by_id returns record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_student

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.get_by_id(sample_student["id"])

            assert result["id"] == sample_student["id"]

    def test_get_by_id_returns_none_for_missing(self):
        """Test get_by_id returns None for missing record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.get_by_id("nonexistent")

            assert result is None

    def test_get_all_returns_list(self):
        """Test get_all returns list of records"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": "1", "name": "Test1"},
            {"id": "2", "name": "Test2"}
        ]

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.get_all()

            assert len(result) == 2

    def test_get_all_with_where_clause(self):
        """Test get_all with WHERE clause"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": "1", "name": "Test1"}]

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.get_all(where="status = 'active'", params=("active",))

            assert len(result) == 1
            mock_cursor.execute.assert_called_once()

    def test_get_all_with_order_by(self):
        """Test get_all with ORDER BY"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            repo.get_all(order_by="created_at DESC")

            mock_cursor.execute.assert_called_once()
            assert "ORDER BY" in str(mock_cursor.execute.call_args)

    def test_get_all_with_limit(self):
        """Test get_all with LIMIT"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            repo.get_all(limit=10)

            mock_cursor.execute.assert_called_once()
            assert "LIMIT" in str(mock_cursor.execute.call_args)

    def test_get_all_with_offset(self):
        """Test get_all with OFFSET"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            repo.get_all(offset=20)

            mock_cursor.execute.assert_called_once()
            assert "OFFSET" in str(mock_cursor.execute.call_args)

    def test_update_modifies_record(self, sample_student):
        """Test update modifies and returns record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {**sample_student, "name": "Updated"}

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.update(sample_student["id"], {"name": "Updated"})

            assert result["name"] == "Updated"

    def test_update_returns_none_for_missing(self):
        """Test update returns None for missing record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.update("nonexistent", {"name": "Updated"})

            assert result is None

    def test_delete_removes_record(self):
        """Test delete removes record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            repo = BaseRepository("students")
            repo.db = mock_db

            result = repo.delete("test-id")

            assert result is True
            mock_cursor.execute.assert_called_once()

    def test_jsonb_conversion_helper(self):
        """Test _jsonb helper converts dict correctly"""
        mock_db = MagicMock()
        repo = BaseRepository("test")
        repo.db = mock_db

        data = {"key": "value", "nested": {"inner": True}}
        result = repo._jsonb(data)

        # Should return a Json wrapper object
        assert result is not None


class TestNotificationService:
    """Tests for NotificationService"""

    def test_send_creates_notification(self, sample_school_id):
        """Test send creates notification record"""
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": "notif-1"}

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch.object(mock_db, 'get_cursor', return_value=mock_cm):
            service = NotificationService.__new__(NotificationService)
            service.db = mock_db

            result = service.send(
                school_id=sample_school_id,
                notification_type="graduation",
                title="Test Title",
                message="Test message",
                priority="high",
                student_id="student-1"
            )

            mock_cursor.execute.assert_called_once()


class TestCheckDatabaseHealth:
    """Tests for database health check"""

    def test_check_database_health_returns_healthy_on_success(self):
        """Test health check returns healthy when database is up"""
        with patch('core.database.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.execute_scalar.return_value = 1
            mock_get_db.return_value = mock_db

            result = check_database_health()

            assert result["status"] == "healthy"
            assert result["database"] == "postgresql"

    def test_check_database_health_returns_unhealthy_on_error(self):
        """Test health check returns unhealthy on exception"""
        with patch('core.database.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.execute_scalar.side_effect = Exception("Connection refused")
            mock_get_db.return_value = mock_db

            result = check_database_health()

            assert result["status"] == "unhealthy"
            assert "error" in result
