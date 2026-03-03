"""Communication app activity tracker.

Detects when the user is actively using communication tools
(Slack, email, Teams, etc.) and records the window context.
"""

import logging
import time
from datetime import datetime

from activity_monitor.monitors.application import get_active_window_info
from activity_monitor.monitors.base import BaseMonitor
from activity_monitor.storage.models import CommunicationEvent

logger = logging.getLogger(__name__)


def _extract_context(app: str, window_title: str) -> str:
    """Try to extract useful context from the window title.

    E.g., Slack window titles often contain "#channel-name" or "DM with Name".
    Email clients may show subject lines.
    """
    if not window_title:
        return ""

    # Slack: "Channel - Workspace" or "Person - Workspace"
    if "slack" in app.lower():
        parts = window_title.split(" - ")
        if parts:
            return parts[0].strip()

    # Teams: "Chat | Microsoft Teams" or "Channel | Microsoft Teams"
    if "teams" in app.lower():
        parts = window_title.split(" | ")
        if parts:
            return parts[0].strip()

    # Discord: "#channel - Server" or "DM"
    if "discord" in app.lower():
        parts = window_title.split(" - ")
        if parts:
            return parts[0].strip()

    # Email clients: usually show the subject or inbox
    email_apps = ["outlook", "mail", "thunderbird", "gmail"]
    if any(e in app.lower() for e in email_apps):
        # Often "Subject - AppName" or "Inbox - email@addr - AppName"
        parts = window_title.split(" - ")
        if parts:
            return parts[0].strip()

    return window_title[:200]


class CommunicationMonitor(BaseMonitor):
    """Tracks time spent in communication applications."""

    def __init__(self, config: dict, db_session_factory):
        super().__init__(config, db_session_factory)
        comm_config = config.get("monitoring", {}).get("communications", {})
        self._tracked_apps = [
            a.lower() for a in comm_config.get("tracked_apps", [])
        ]
        self._poll_interval = config.get("monitoring", {}).get(
            "applications", {}
        ).get("poll_interval_seconds", 5)

    def _is_communication_app(self, app_name: str) -> bool:
        lower = app_name.lower()
        return any(tracked in lower for tracked in self._tracked_apps)

    def _run(self):
        in_comm = False
        comm_app = ""
        comm_window = ""
        comm_start = None

        while self._running:
            app_name, window_title = get_active_window_info()

            if self._is_communication_app(app_name):
                if not in_comm or app_name != comm_app or window_title != comm_window:
                    # Save previous communication session
                    if in_comm and comm_start:
                        duration = (datetime.utcnow() - comm_start).total_seconds()
                        self._record_event(comm_app, comm_window, duration)

                    in_comm = True
                    comm_app = app_name
                    comm_window = window_title
                    comm_start = datetime.utcnow()
            else:
                if in_comm and comm_start:
                    duration = (datetime.utcnow() - comm_start).total_seconds()
                    self._record_event(comm_app, comm_window, duration)
                    in_comm = False
                    comm_start = None

            time.sleep(self._poll_interval)

        # Final flush
        if in_comm and comm_start:
            duration = (datetime.utcnow() - comm_start).total_seconds()
            self._record_event(comm_app, comm_window, duration)

    def _record_event(self, app: str, window: str, duration: float):
        if duration < 2:
            return

        context = _extract_context(app, window)

        session = self._get_session()
        try:
            record = CommunicationEvent(
                application=app[:200],
                window_title=window[:500],
                duration_seconds=duration,
                context=context[:500],
            )
            session.add(record)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to record communication event")
        finally:
            session.close()
