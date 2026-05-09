# Database Module
# Production-grade PostgreSQL connection with connection pooling

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, date
from typing import Any, Dict, Generator, List, Optional

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor, Json

from core.config import get_settings


class Database:
    """PostgreSQL connection pool manager"""

    _instance: Optional["Database"] = None
    _pool: Optional[pool.ThreadedConnectionPool] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            settings = get_settings()
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=settings.database.pool_size + settings.database.max_overflow,
                dsn=settings.database.url,
                async_=False
            )

    @contextmanager
    def get_connection(self) -> Generator:
        """Get a connection from the pool"""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor) -> Generator:
        """Get a cursor with automatic connection management"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def execute(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[List[Dict]]:
        """Execute a query and return results"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            return None

    def execute_one(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Dict]:
        """Execute a query and return single result"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchone()
            return None

    def execute_scalar(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Any]:
        """Execute a query and return scalar value"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else None

    def close(self):
        """Close all connections in the pool"""
        if self._pool:
            self._pool.closeall()
            self._pool = None


def get_db() -> Database:
    """Get database instance"""
    return Database()


# ============================================
# Repository Pattern - Base Class
# ============================================

class BaseRepository:
    """Base repository with common CRUD operations"""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.db = get_db()

    def _jsonb(self, data: Any) -> Json:
        """Convert Python dict to PostgreSQL JSONB"""
        return Json(data)

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new record"""
        columns = list(data.keys())
        values = list(data.values())

        # Convert UUIDs to strings
        values = [
            str(v) if isinstance(v, uuid.UUID) else
            self._jsonb(v) if isinstance(v, dict) else
            v for v in values
        ]

        query = sql.SQL("""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
            RETURNING *
        """).format(
            table=sql.Identifier(self.table_name),
            columns=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            placeholders=sql.SQL(", ").join(sql.Placeholder() * len(columns))
        )

        result = self.db.execute_one(str(query), tuple(values))
        return dict(result) if result else {}

    def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Get record by ID"""
        query = sql.SQL("SELECT * FROM {table} WHERE id = %s").format(
            table=sql.Identifier(self.table_name)
        )
        result = self.db.execute_one(str(query), (str(id),))
        return dict(result) if result else None

    def get_all(
        self,
        where: Optional[str] = None,
        params: Optional[tuple] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all records with optional filtering"""
        query = sql.SQL("SELECT * FROM {table}").format(
            table=sql.Identifier(self.table_name)
        )

        if where:
            query = sql.SQL("{query} WHERE {where}").format(
                query=query,
                where=sql.SQL(where)
            )

        if order_by:
            query = sql.SQL("{query} ORDER BY {order_by}").format(
                query=query,
                order_by=sql.SQL(order_by)
            )

        if limit:
            query = sql.SQL("{query} LIMIT {limit}").format(
                query=query,
                limit=sql.Placeholder()
            )

        if offset:
            query = sql.SQL("{query} OFFSET {offset}").format(
                query=query,
                offset=sql.Placeholder()
            )

        return [dict(r) for r in self.db.execute(str(query), params or ())]

    def update(self, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record by ID"""
        columns = list(data.keys())
        values = [
            str(v) if isinstance(v, uuid.UUID) else
            self._jsonb(v) if isinstance(v, dict) else
            v for v in data.values()
        ]

        query = sql.SQL("""
            UPDATE {table}
            SET {set_clause}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """).format(
            table=sql.Identifier(self.table_name),
            set_clause=sql.SQL(", ").join(
                sql.SQL("{} = {}".format(sql.Identifier(c), sql.Placeholder()))
                for c in columns
            )
        )

        result = self.db.execute_one(str(query), tuple(values) + (str(id),))
        return dict(result) if result else None

    def delete(self, id: str) -> bool:
        """Delete a record by ID"""
        query = sql.SQL("DELETE FROM {table} WHERE id = %s").format(
            table=sql.Identifier(self.table_name)
        )
        self.db.execute(str(query), (str(id),))
        return True


# ============================================
# Notification Helper
# ============================================

class NotificationService:
    """Send notifications to owner"""

    def __init__(self):
        self.db = get_db()

    def send(
        self,
        school_id: str,
        notification_type: str,
        title: str,
        message: str,
        priority: str = "normal",
        student_id: Optional[str] = None
    ) -> str:
        """Send a notification"""
        data = {
            "school_id": school_id,
            "student_id": student_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "priority": priority
        }
        repo = BaseRepository("notifications")
        result = repo.create(data)
        return result.get("id", "")


# ============================================
# Health Check
# ============================================

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity"""
    try:
        db = get_db()
        result = db.execute_scalar("SELECT 1")
        return {
            "status": "healthy" if result == 1 else "unhealthy",
            "database": "postgresql"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(e)
        }
