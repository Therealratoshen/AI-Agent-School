# Dashboard API - REST API for dashboard data

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, Optional
from flask import Flask, jsonify, request
from shared import setup_logging

logger = setup_logging(__name__)

class DashboardAPI:
    """
    Dashboard REST API
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes"""

        @self.app.route('/api/status')
        def status():
            return jsonify({
                "status": "running",
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            })

        @self.app.route('/api/progress')
        def progress():
            return jsonify({
                "student_id": "demo-student",
                "status": "training",
                "current_lesson": 2,
                "lessons_completed": ["cron_01"],
                "total_lessons": 5,
                "progress_percent": 20
            })

        @self.app.route('/api/memory/health')
        def memory_health():
            return jsonify({
                "healthy": True,
                "score": 85,
                "files": 5,
                "corrections_count": 3
            })

        @self.app.route('/api/mistakes')
        def mistakes():
            return jsonify({
                "total": 3,
                "active": 2,
                "learned": 1,
                "escalated": 0,
                "items": [
                    {
                        "id": "mist_001",
                        "mistake": "Wrong cron syntax",
                        "count": 2,
                        "severity": "medium"
                    }
                ]
            })

        @self.app.route('/api/cron/status')
        def cron_status():
            return jsonify({
                "total_jobs": 3,
                "healthy": 2,
                "warning": 1,
                "failed": 0,
                "jobs": [
                    {"name": "backup-db", "status": "ok", "last_heartbeat": "2 min ago"},
                    {"name": "sync-files", "status": "warning", "last_heartbeat": "12 min ago"},
                    {"name": "cleanup-logs", "status": "ok", "last_heartbeat": "1 min ago"}
                ]
            })

        @self.app.route('/api/activity')
        def activity():
            return jsonify({
                "recent": [
                    {"time": "10:30", "event": "Lesson 2 delivered", "type": "lesson"},
                    {"time": "10:35", "event": "Quiz submitted", "type": "quiz"},
                    {"time": "10:40", "event": "Correction applied", "type": "correction"}
                ]
            })

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        """Run the API server"""
        self.app.run(host=host, port=port, debug=False)

def create_dashboard_api(config: Dict[str, Any]) -> DashboardAPI:
    """Create dashboard API instance"""
    return DashboardAPI(config)
