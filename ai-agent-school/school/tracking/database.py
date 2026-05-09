# Mistake Database - SQLite storage for mistakes

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime
from shared import timestamp, ensure_dir, setup_logging

logger = setup_logging(__name__, "./logs/mistake_db.log")

class MistakeDB:
    """
    SQLite database for storing mistakes and corrections
    """

    def __init__(self, db_path: str = "./data/mistakes.db"):
        self.db_path = db_path
        ensure_dir(os.path.dirname(db_path))
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mistakes (
                id TEXT PRIMARY KEY,
                mistake TEXT NOT NULL,
                correct_answer TEXT,
                context TEXT,
                severity TEXT DEFAULT 'medium',
                count INTEGER DEFAULT 1,
                first_seen TEXT,
                last_seen TEXT,
                escalated INTEGER DEFAULT 0,
                learned INTEGER DEFAULT 0,
                learned_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                mistake_id TEXT,
                correction TEXT NOT NULL,
                applied_at TEXT,
                verified INTEGER DEFAULT 0,
                verified_at TEXT,
                FOREIGN KEY (mistake_id) REFERENCES mistakes (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_results (
                id TEXT PRIMARY KEY,
                lesson_id TEXT,
                score REAL,
                correct INTEGER,
                total INTEGER,
                submitted_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

        logger.info(f"Database initialized: {self.db_path}")

    def insert_mistake(self, mistake_data: Dict[str, Any]) -> str:
        """Insert a new mistake"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO mistakes (id, mistake, correct_answer, context, severity,
                               count, first_seen, last_seen, escalated, learned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            mistake_data['id'],
            mistake_data['mistake'],
            mistake_data.get('correct_answer', ''),
            mistake_data.get('context', ''),
            mistake_data.get('severity', 'medium'),
            mistake_data.get('count', 1),
            mistake_data.get('first_seen', timestamp()),
            mistake_data.get('last_seen', timestamp()),
            0,
            0
        ))

        conn.commit()
        conn.close()

        return mistake_data['id']

    def update_mistake(self, mistake_id: str, updates: Dict[str, Any]) -> bool:
        """Update a mistake"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [mistake_id]

        cursor.execute(f'UPDATE mistakes SET {set_clause} WHERE id = ?', values)
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    def get_mistake(self, mistake_id: str) -> Optional[Dict[str, Any]]:
        """Get a mistake by ID"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM mistakes WHERE id = ?', (mistake_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_all_mistakes(self, filter_type: str = "all") -> List[Dict[str, Any]]:
        """Get all mistakes, optionally filtered"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if filter_type == "escalated":
            cursor.execute('SELECT * FROM mistakes WHERE escalated = 1 AND learned = 0')
        elif filter_type == "learned":
            cursor.execute('SELECT * FROM mistakes WHERE learned = 1')
        elif filter_type == "active":
            cursor.execute('SELECT * FROM mistakes WHERE learned = 0')
        else:
            cursor.execute('SELECT * FROM mistakes')

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def insert_correction(self, correction_data: Dict[str, Any]) -> str:
        """Insert a correction"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO corrections (id, mistake_id, correction, applied_at)
            VALUES (?, ?, ?, ?)
        ''', (
            correction_data['id'],
            correction_data.get('mistake_id'),
            correction_data['correction'],
            timestamp()
        ))

        conn.commit()
        conn.close()

        return correction_data['id']

    def get_corrections_for_mistake(self, mistake_id: str) -> List[Dict[str, Any]]:
        """Get all corrections for a mistake"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM corrections WHERE mistake_id = ?', (mistake_id,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def insert_quiz_result(self, result_data: Dict[str, Any]) -> str:
        """Insert a quiz result"""
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO quiz_results (id, lesson_id, score, correct, total, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            result_data['id'],
            result_data['lesson_id'],
            result_data['score'],
            result_data['correct'],
            result_data['total'],
            timestamp()
        ))

        conn.commit()
        conn.close()

        return result_data['id']
