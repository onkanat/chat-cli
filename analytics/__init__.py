from __future__ import annotations

from .manager import AnalyticsManager
from .views import (
    display_analytics_dashboard,
    display_real_time_monitoring,
    generate_analytics_report,
)

__all__ = [
    "AnalyticsManager",
    "display_analytics_dashboard",
    "display_real_time_monitoring",
    "generate_analytics_report",
]
