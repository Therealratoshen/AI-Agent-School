# MCP connection tests

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="module")
def mcp_app():
    """Flask test app with local MCP routes."""
    tmpdir = tempfile.mkdtemp(prefix="mcp-test-")
    comm = os.path.join(tmpdir, "comm")
    memory = os.path.join(tmpdir, "memory")

    config = {
        "communication": {
            "base_dir": comm,
            "to_student": os.path.join(comm, "to_student"),
            "from_student": os.path.join(comm, "from_student"),
            "poll_interval": 1,
        },
        "memory": {"student_memory_path": memory},
        "tracking": {"log_path": os.path.join(tmpdir, "logs"), "db_path": os.path.join(tmpdir, "mistakes.db")},
        "teacher": {"name": "Teacher", "default_topic": "cron_handling"},
        "cron": {"monitored_jobs": []},
    }

    from school.main import AISchoolServer
    from school.teacher import TeacherAgent
    from school.student import StudentReceiver, ProgressTracker
    from school.tracking import MistakeDetector
    from school.teaching_loop import TeachingLoop
    from school.memory import MemoryPersistence, BackupManager, MemoryHealthCheck
    from school.cron import CronMonitor, FailureDetector, AutoHealer, DeadLetterQueue
    from school.benchmark import BenchmarkRunner
    from school.dashboard.api import create_dashboard_api

    server = AISchoolServer.__new__(AISchoolServer)
    server.config = config
    server._setup_directories = AISchoolServer._setup_directories.__get__(server)
    server._setup_directories()

    server.teacher = TeacherAgent(config)
    server.student_receiver = StudentReceiver(config)
    server.progress_tracker = ProgressTracker(os.path.join(tmpdir, "data"))
    server.memory_sync = __import__("school.student.memory_sync", fromlist=["MemorySync"]).MemorySync(config)
    server.memory_persistence = MemoryPersistence(config)
    server.backup_manager = BackupManager(config)
    server.memory_health = MemoryHealthCheck(config)
    server.cron_monitor = CronMonitor(config)
    server.failure_detector = FailureDetector(config)
    server.auto_healer = AutoHealer(config)
    server.dead_letter_queue = DeadLetterQueue(config)
    server.mistake_detector = MistakeDetector(config)
    server.teaching_loop = TeachingLoop(server)
    server.benchmark_runner = BenchmarkRunner()
    server.dashboard_api = create_dashboard_api(server)

    yield server.dashboard_api.app, server, memory, tmpdir


def _call_tool(client, api_key, tool_name, arguments=None):
    resp = client.post(
        "/api/mcp/agents/chat",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    data = resp.get_json()
    text = data["result"]["content"][0]["text"]
    return json.loads(text)


class TestLocalMCPServer:
    def test_register_agent(self, mcp_app):
        app, _server, _memory, _tmpdir = mcp_app
        client = app.test_client()
        resp = client.post("/api/mcp/agents", json={"agent_id": "test-agent", "agent_name": "Test"})
        result = resp.get_json()
        assert resp.status_code == 200
        assert result["api_key"].startswith("local_")

    def test_mcp_list_courses(self, mcp_app):
        app, _server, _memory, _tmpdir = mcp_app
        client = app.test_client()
        reg = client.post("/api/mcp/agents", json={"agent_id": "t1", "agent_name": "T1"}).get_json()
        courses = _call_tool(client, reg["api_key"], "list_courses")
        assert courses["courses"][0]["course_id"] == "cron_handling"

    def test_mcp_enroll_and_lesson(self, mcp_app):
        app, _server, _memory, _tmpdir = mcp_app
        client = app.test_client()
        reg = client.post("/api/mcp/agents", json={"agent_id": "t2", "agent_name": "T2"}).get_json()
        key = reg["api_key"]
        _call_tool(client, key, "enroll", {"course_id": "cron_handling", "agent_id": "t2", "agent_name": "T2"})
        lesson = _call_tool(client, key, "get_lesson", {"course_id": "cron_handling", "lesson_number": 1})
        assert lesson["lesson_id"] == "cron_01"
        assert "Cron Fundamentals" in lesson["title"]

    def test_mcp_submit_quiz(self, mcp_app):
        app, _server, _memory, _tmpdir = mcp_app
        client = app.test_client()
        reg = client.post("/api/mcp/agents", json={"agent_id": "t3", "agent_name": "T3"}).get_json()
        key = reg["api_key"]
        _call_tool(client, key, "enroll", {"course_id": "cron_handling", "agent_id": "t3", "agent_name": "T3"})
        lesson = _call_tool(client, key, "get_lesson", {"course_id": "cron_handling", "lesson_number": 1})
        answers = {q["question_id"]: lesson["quiz"]["answers_key"][q["question_id"]]
                   for q in lesson["quiz"]["questions"]}
        result = _call_tool(client, key, "submit_quiz", {
            "course_id": "cron_handling", "lesson_number": 1, "answers": answers,
        })
        assert result["passed"] is True


class TestMCPConnector:
    def test_mcp_connector_mode(self, mcp_app):
        from student_agent.connector import MCPConnector
        from student_agent.mcp_client import MCPClient

        _app, server, memory, _tmpdir = mcp_app
        reg = server.dashboard_api.mcp_registry.register("connector-test", "Connector Test")
        config = {
            "communication": {"method": "mcp"},
            "mcp": {
                "base_url": "http://test",
                "api_key": reg["api_key"],
                "agent_id": "connector-test",
            },
            "memory": {"student_memory_path": memory},
        }
        connector = MCPConnector(config)
        connector.client.ensure_enrolled = lambda *a, **k: {"enrollment_id": "enr_test"}
        connector.client.get_lesson = lambda n: server.dashboard_api.mcp_handler.handle(
            reg["api_key"], "get_lesson", {"lesson_number": 1}
        )
        connector._enrolled = True
        connector._fetch_lesson(1)
        messages = connector.poll_messages()
        assert messages[0]["type"] == "lesson"

    def test_student_agent_file_mode_still_works(self):
        from student_agent.connector import FileConnector
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            to_s = os.path.join(tmpdir, "to_student")
            from_s = os.path.join(tmpdir, "from_student")
            os.makedirs(to_s)
            os.makedirs(from_s)
            config = {"communication": {"method": "file", "to_student": to_s, "from_student": from_s}}
            assert FileConnector(config).mode == "file"


class TestConnectorFactory:
    def test_file_connector_default(self):
        from student_agent.connector import get_connector, FileConnector
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            to_s = os.path.join(tmpdir, "to_student")
            from_s = os.path.join(tmpdir, "from_student")
            os.makedirs(to_s)
            os.makedirs(from_s)
            config = {"communication": {"method": "file", "to_student": to_s, "from_student": from_s}}
            assert isinstance(get_connector(config), FileConnector)

    def test_mcp_connector(self):
        from student_agent.connector import get_connector, MCPConnector

        config = {
            "communication": {"method": "mcp"},
            "mcp": {"base_url": "http://localhost:8080/api/mcp"},
            "memory": {"student_memory_path": "/tmp/mem"},
        }
        assert isinstance(get_connector(config), MCPConnector)
