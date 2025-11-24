from __future__ import annotations

from typing import Dict, Any
from datetime import datetime, timedelta
import json
from pathlib import Path


DEFAULT_ANALYTICS = Path("analytics.json")


class AnalyticsManager:
    """Manages conversation analytics and monitoring."""

    def __init__(self, analytics_file: Path = DEFAULT_ANALYTICS):
        self.analytics_file = analytics_file
        self.data = self.load_analytics()

    def load_analytics(self) -> Dict[str, Any]:
        """Load analytics data from file."""
        if self.analytics_file.exists():
            try:
                with open(self.analytics_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "sessions": [],
            "total_messages": 0,
            "total_tokens": 0,
            "total_response_time": 0.0,
            "models_used": {},
            "commands_used": {},
            "daily_usage": {},
            "created_at": datetime.now().isoformat(),
        }

    def save_analytics(self) -> None:
        """Save analytics data to file."""
        try:
            with open(self.analytics_file, "w") as f:
                json.dump(self.data, f, indent=2, default=str)
        except Exception:
            pass

    def track_message(
        self,
        role: str,
        content: str,
        model: str,
        response_time: float = 0.0,
        tokens: int = 0,
    ) -> None:
        """Track a message in analytics."""
        self.data["total_messages"] += 1
        self.data["total_tokens"] += tokens
        self.data["total_response_time"] += response_time

        # Track model usage
        if model not in self.data["models_used"]:
            self.data["models_used"][model] = {
                "count": 0,
                "tokens": 0,
                "avg_response_time": 0.0,
            }

        model_stats = self.data["models_used"][model]
        model_stats["count"] += 1
        model_stats["tokens"] += tokens

        # Update average response time
        total_count = sum(stats["count"] for stats in self.data["models_used"].values())
        model_stats["avg_response_time"] = (
            model_stats["avg_response_time"] * (total_count - 1) + response_time
        ) / total_count

        # Track daily usage
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.data["daily_usage"]:
            self.data["daily_usage"][today] = {"messages": 0, "tokens": 0}

        self.data["daily_usage"][today]["messages"] += 1
        self.data["daily_usage"][today]["tokens"] += tokens

        self.save_analytics()

    def track_command(self, command: str) -> None:
        """Track command usage."""
        if command not in self.data["commands_used"]:
            self.data["commands_used"][command] = 0
        self.data["commands_used"][command] += 1
        self.save_analytics()

    def start_session(self, model: str) -> str:
        """Start a new session."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session = {
            "id": session_id,
            "start_time": datetime.now().isoformat(),
            "model": model,
            "messages": 0,
            "tokens": 0,
            "commands": [],
        }
        self.data["sessions"].append(session)
        self.save_analytics()
        return session_id

    def end_session(self, session_id: str) -> None:
        """End a session."""
        for session in self.data["sessions"]:
            if session["id"] == session_id:
                session["end_time"] = datetime.now().isoformat()
                session["duration"] = (
                    datetime.fromisoformat(session["end_time"]) - datetime.fromisoformat(session["start_time"])
                ).total_seconds()
                break
        self.save_analytics()

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        # Calculate averages
        avg_response_time = 0.0
        if self.data["total_messages"] > 0:
            avg_response_time = self.data["total_response_time"] / self.data["total_messages"]

        # Most used model
        most_used_model = None
        max_count = 0
        for model, stats in self.data["models_used"].items():
            if stats["count"] > max_count:
                max_count = stats["count"]
                most_used_model = model

        # Most used command
        most_used_command = None
        max_cmd_count = 0
        for cmd, count in self.data["commands_used"].items():
            if count > max_cmd_count:
                max_cmd_count = count
                most_used_command = cmd

        # Last 7 days usage
        last_7_days = {}
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.data["daily_usage"]:
                last_7_days[date] = self.data["daily_usage"][date]

        return {
            "total_messages": self.data["total_messages"],
            "total_tokens": self.data["total_tokens"],
            "avg_response_time": avg_response_time,
            "most_used_model": most_used_model,
            "most_used_command": most_used_command,
            "models_used": self.data["models_used"],
            "commands_used": self.data["commands_used"],
            "last_7_days": last_7_days,
            "total_sessions": len(self.data["sessions"]),
        }
