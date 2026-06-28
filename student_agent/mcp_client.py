# MCP HTTP client — works with cloud OR local school server

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.error

from shared import setup_logging, read_json, write_json, ensure_dir

logger = setup_logging(__name__)

DEFAULT_CLOUD_URL = "https://shortcutsistem.com/api/mcp"
DEFAULT_LOCAL_URL = "http://localhost:8080/api/mcp"


class MCPClient:
    """
    HTTP client for AI Agent School MCP API.
    Same interface for cloud (shortcutsistem.com) and local school server.
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        agent_id: str = None,
        agent_name: str = None,
        credentials_path: str = "./data/student_memory/mcp_credentials.json",
    ):
        self.base_url = (base_url or os.environ.get("AI_SCHOOL_MCP_URL") or DEFAULT_LOCAL_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("AI_SCHOOL_API_KEY")
        self.agent_id = agent_id or os.environ.get("AI_SCHOOL_AGENT_ID", "student-agent")
        self.agent_name = agent_name or os.environ.get("AI_SCHOOL_AGENT_NAME", "Student Agent")
        self.credentials_path = credentials_path
        self.enrollment_id: Optional[str] = None
        self.course_id: Optional[str] = None
        self._request_id = 0
        self._load_credentials()

    def _load_credentials(self) -> None:
        if self.api_key:
            return
        if os.path.exists(self.credentials_path):
            creds = read_json(self.credentials_path, {})
            self.api_key = creds.get("api_key")
            self.enrollment_id = creds.get("enrollment_id")
            self.course_id = creds.get("course_id")
            self.agent_id = creds.get("agent_id", self.agent_id)

    def _save_credentials(self) -> None:
        ensure_dir(os.path.dirname(self.credentials_path))
        write_json(self.credentials_path, {
            "api_key": self.api_key,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "enrollment_id": self.enrollment_id,
            "course_id": self.course_id,
            "base_url": self.base_url,
        })

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _request(self, method: str, path: str, body: Dict = None, auth: bool = True) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"MCP HTTP error {e.code}: {error_body}")
            raise MCPError(f"HTTP {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            logger.error(f"MCP connection error: {e}")
            raise MCPError(f"Connection failed: {e}") from e

    def register(self) -> Dict[str, Any]:
        result = self._request("POST", "/agents", {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
        }, auth=False)
        self.api_key = result.get("api_key")
        self._save_credentials()
        logger.info(f"MCP registered: {self.agent_id}")
        return result

    def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.api_key:
            self.register()

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        response = self._request("POST", "/agents/chat", payload)

        if "error" in response:
            raise MCPError(response["error"].get("message", str(response["error"])))

        result = response.get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result

    def ensure_enrolled(self, course_id: str = "cron_handling") -> Dict[str, Any]:
        if self.enrollment_id:
            return {"enrollment_id": self.enrollment_id, "course_id": self.course_id}

        courses = self.call_tool("list_courses")
        if not courses.get("courses"):
            raise MCPError("No courses available")

        course_id = course_id or courses["courses"][0]["course_id"]
        enrolled = self.call_tool("enroll", {
            "course_id": course_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
        })
        self.enrollment_id = enrolled.get("enrollment_id")
        self.course_id = course_id
        self._save_credentials()
        return enrolled

    def get_lesson(self, lesson_number: int) -> Dict[str, Any]:
        return self.call_tool("get_lesson", {
            "course_id": self.course_id or "cron_handling",
            "lesson_number": lesson_number,
        })

    def submit_quiz(self, lesson_number: int, answers: Dict[str, str]) -> Dict[str, Any]:
        return self.call_tool("submit_quiz", {
            "course_id": self.course_id or "cron_handling",
            "lesson_number": lesson_number,
            "answers": answers,
        })

    def chat(self, message: str) -> Dict[str, Any]:
        return self.call_tool("chat", {
            "course_id": self.course_id or "cron_handling",
            "enrollment_id": self.enrollment_id,
            "message": message,
        })

    def get_progress(self) -> Dict[str, Any]:
        return self.call_tool("get_progress")

    def run_benchmark(self, answers: Dict[str, str] = None) -> Dict[str, Any]:
        args = {}
        if answers:
            args["answers"] = answers
        return self.call_tool("run_benchmark", args)

    def check_graduation(self) -> Dict[str, Any]:
        return self.call_tool("check_graduation", {
            "course_id": self.course_id or "cron_handling",
        })

    def graduate(self) -> Dict[str, Any]:
        return self.call_tool("graduate", {
            "course_id": self.course_id or "cron_handling",
        })


class MCPError(Exception):
    pass
