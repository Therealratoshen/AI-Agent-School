# Dashboard API - REST API for dashboard and teaching control

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Any, Dict
from flask import Flask, jsonify, request
from shared import setup_logging

logger = setup_logging(__name__)


class DashboardAPI:
    """Dashboard REST API with live teaching endpoints."""

    def __init__(self, server: Any):
        self.server = server
        self.config = server.config
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/api/status")
        def status():
            return jsonify({
                "status": "running",
                "teacher": self.server.teacher.name,
                "topic": self.server.teacher.topic,
            })

        @self.app.route("/api/enroll", methods=["POST"])
        def enroll():
            data = request.get_json(silent=True) or {}
            student_id = data.get("student_id", "student-1")
            result = self.server.enroll_student(student_id)
            return jsonify(result)

        @self.app.route("/api/progress")
        def progress():
            return jsonify(self.server.get_progress())

        @self.app.route("/api/lessons/next", methods=["POST"])
        def next_lesson():
            result = self.server.deliver_next_lesson()
            return jsonify(result)

        @self.app.route("/api/memory/health")
        def memory_health():
            health = self.server.memory_health.check()
            return jsonify(health)

        @self.app.route("/api/mistakes")
        def mistakes():
            stats = self.server.mistake_detector.get_statistics()
            return jsonify({
                **stats,
                "items": self.server.mistake_detector.get_mistakes("active"),
            })

        @self.app.route("/api/cron/status")
        def cron_status():
            return jsonify(self.server.cron_monitor.check_all_jobs())

        @self.app.route("/api/activity")
        def activity():
            progress = self.server.get_progress()
            return jsonify({
                "student_id": progress.get("student_id"),
                "lessons_completed": progress.get("lessons_completed", []),
                "current_lesson": progress.get("current_lesson"),
                "progress_percent": progress.get("progress_percent", 0),
            })

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        self.app.run(host=host, port=port, debug=False, use_reloader=False)


def create_dashboard_api(server: Any) -> DashboardAPI:
    return DashboardAPI(server)
