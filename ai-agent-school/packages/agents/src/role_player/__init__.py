from typing import Optional
from datetime import datetime


ROLE_PLAYER_PROMPT = """You are an AI Role-Player Agent at AI Agent School.

Your role is to simulate real-world scenarios for student practice.

Simulated Roles:
1. System Administrator - Reports cron job issues
2. API Service - Responds to health check pings
3. Database - Confirms backup completion
4. User - Requests new cron jobs
5. Monitoring System - Sends alerts

Scenario Types:
- Cron job fails silently for 1 week
- API endpoint stops responding
- Disk becomes full during backup
- Network timeout during scheduled task
- External service changes API version

When running a scenario:
1. Set up the scenario context
2. Play the role consistently
3. React realistically to student actions
4. Provide feedback on student performance
5. Document learning points
"""


class RolePlayerAgent:
    def __init__(
        self,
        name: str = "RolePlayer",
        primary_llm: str = "minimax",
    ):
        self.name = name
        self.primary_llm = primary_llm
        self.prompt = ROLE_PLAYER_PROMPT
        self.active_scenario: Optional[dict] = None

    async def start_scenario(self, scenario_type: str, context: dict) -> dict:
        scenario_configs = {
            "silent_failure": {
                "role": "system_admin",
                "setup": "Cron job was supposed to run daily for the past week",
                "expected_student_action": "Detect missing heartbeats and investigate",
            },
            "api_timeout": {
                "role": "api_service",
                "setup": "API endpoint is slow to respond",
                "expected_student_action": "Implement timeout and retry logic",
            },
            "disk_full": {
                "role": "database",
                "setup": "Disk space exhausted during backup",
                "expected_student_action": "Add disk space monitoring and cleanup",
            },
        }

        config = scenario_configs.get(scenario_type, scenario_configs["silent_failure"])

        self.active_scenario = {
            "type": scenario_type,
            "role": config["role"],
            "context": context,
            "started_at": datetime.utcnow().isoformat(),
        }

        return {
            "status": "started",
            "scenario": self.active_scenario,
            "role_introduction": f"You are a {config['role']}. {config['setup']}",
            "expected_action": config["expected_student_action"],
        }

    async def respond_to_action(self, action: str) -> dict:
        if not self.active_scenario:
            return {"error": "No active scenario"}

        scenario_type = self.active_scenario["type"]

        responses = {
            "silent_failure": {
                "check_heartbeat": "No response from cron job in 7 days",
                "restart_job": "Job restarted, but no heartbeat after 1 hour",
                "check_logs": "Logs show job was marked as completed but didn't run",
            },
            "api_timeout": {
                "call_api": "Request timed out after 30 seconds",
                "retry": "Still timing out on retry attempt",
                "check_status": "Service reports all systems normal",
            },
        }

        response = responses.get(scenario_type, {}).get(action, "No specific response for this action")

        return {
            "scenario_type": scenario_type,
            "action": action,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def end_scenario(self) -> dict:
        if not self.active_scenario:
            return {"status": "no_scenario"}

        summary = {
            "status": "completed",
            "scenario": self.active_scenario,
            "ended_at": datetime.utcnow().isoformat(),
        }
        self.active_scenario = None
        return summary
