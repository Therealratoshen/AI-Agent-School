# Dashboard API - REST API for dashboard and teaching control

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Any, Dict
from flask import Flask, jsonify, request
from shared import setup_logging
from school.mcp import MCPRegistry, MCPToolHandler

logger = setup_logging(__name__)


class DashboardAPI:
    """Dashboard REST API with live teaching endpoints."""

    def __init__(self, server: Any):
        self.server = server
        self.config = server.config
        self.app = Flask(__name__)
        self.mcp_registry = MCPRegistry("./data")
        self.mcp_handler = MCPToolHandler(server, self.mcp_registry)
        self._setup_routes()
        self._setup_mcp_routes()

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

        @self.app.route("/api/benchmark/tasks")
        def benchmark_tasks():
            return jsonify({"tasks": self.server.get_benchmark_tasks()})

        @self.app.route("/api/benchmark/run", methods=["POST"])
        def benchmark_run():
            data = request.get_json(silent=True) or {}
            answers = data.get("answers", {})
            baseline = data.get("baseline_percentage")
            return jsonify(self.server.run_benchmark(answers, baseline_percentage=baseline))

        @self.app.route("/api/benchmark/run-student", methods=["POST"])
        def benchmark_run_student():
            from school.benchmark.solver import solve_from_memory

            memory_path = self.server.config.get("memory", {}).get(
                "student_memory_path", "./data/student_memory"
            )
            answers = solve_from_memory(memory_path)
            return jsonify(self.server.run_benchmark(answers))

    def _setup_mcp_routes(self):
        """MCP-compatible routes — same paths as cloud API."""

        @self.app.route("/api/mcp/agents", methods=["POST"])
        def mcp_register():
            data = request.get_json(silent=True) or {}
            agent_id = data.get("agent_id", f"agent-{id(data)}")
            agent_name = data.get("agent_name", agent_id)
            record = self.mcp_registry.register(agent_id, agent_name)
            return jsonify({
                "agent_id": record["agent_id"],
                "api_key": record["api_key"],
                "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            })

        @self.app.route("/api/mcp/agents/chat", methods=["POST"])
        def mcp_chat():
            api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
            data = request.get_json(silent=True) or {}

            if data.get("method") != "tools/call":
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": data.get("id", 1),
                    "error": {"code": -32601, "message": "Only tools/call supported locally"},
                })

            params = data.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = self.mcp_handler.handle(api_key, tool_name, arguments)
            return jsonify({
                "jsonrpc": "2.0",
                "id": data.get("id", 1),
                "result": {"content": [{"type": "text", "text": __import__("json").dumps(result)}]},
            })

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        self.app.run(host=host, port=port, debug=False, use_reloader=False)


def create_dashboard_api(server: Any) -> DashboardAPI:
    return DashboardAPI(server)
