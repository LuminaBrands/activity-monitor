"""High-level database operations for querying activity data."""

import json
from datetime import datetime, timedelta

from sqlalchemy import func

from activity_monitor.storage.models import (
    ApplicationUsage,
    CommunicationEvent,
    DailySummary,
    Database,
    KeyboardActivity,
    Screenshot,
)


class ActivityDatabase:
    """Provides query methods over the raw activity data."""

    def __init__(self, db_path: str):
        self.db = Database(db_path)

    def get_session(self):
        return self.db.get_session()

    def get_activity_for_date(self, date: str) -> dict:
        """Get all activity data for a given date (YYYY-MM-DD).

        Returns a dict with keys: keyboard, applications, screenshots,
        communications, stats.
        """
        session = self.db.get_session()
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
            day_end = day_start + timedelta(days=1)

            keyboard = (
                session.query(KeyboardActivity)
                .filter(
                    KeyboardActivity.timestamp >= day_start,
                    KeyboardActivity.timestamp < day_end,
                )
                .order_by(KeyboardActivity.timestamp)
                .all()
            )

            apps = (
                session.query(
                    ApplicationUsage.application_name,
                    ApplicationUsage.category,
                    func.sum(ApplicationUsage.duration_seconds).label("total_seconds"),
                    func.count(ApplicationUsage.id).label("session_count"),
                )
                .filter(
                    ApplicationUsage.timestamp >= day_start,
                    ApplicationUsage.timestamp < day_end,
                )
                .group_by(
                    ApplicationUsage.application_name, ApplicationUsage.category
                )
                .order_by(func.sum(ApplicationUsage.duration_seconds).desc())
                .all()
            )

            screenshots = (
                session.query(Screenshot)
                .filter(
                    Screenshot.timestamp >= day_start,
                    Screenshot.timestamp < day_end,
                )
                .order_by(Screenshot.timestamp)
                .all()
            )

            comms = (
                session.query(CommunicationEvent)
                .filter(
                    CommunicationEvent.timestamp >= day_start,
                    CommunicationEvent.timestamp < day_end,
                )
                .order_by(CommunicationEvent.timestamp)
                .all()
            )

            total_keys = sum(k.key_count for k in keyboard)
            active_minutes = len(set(k.minute_bucket for k in keyboard))
            total_app_seconds = sum(a.total_seconds or 0 for a in apps)

            return {
                "date": date,
                "keyboard": [
                    {
                        "timestamp": k.timestamp.isoformat(),
                        "application": k.application,
                        "window_title": k.window_title,
                        "key_count": k.key_count,
                    }
                    for k in keyboard
                ],
                "applications": [
                    {
                        "name": a.application_name,
                        "category": a.category,
                        "total_minutes": round((a.total_seconds or 0) / 60, 1),
                        "sessions": a.session_count,
                    }
                    for a in apps
                ],
                "screenshots": [
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "file_path": s.file_path,
                        "active_app": s.active_application,
                        "window_title": s.active_window_title,
                    }
                    for s in screenshots
                ],
                "communications": [
                    {
                        "timestamp": c.timestamp.isoformat(),
                        "application": c.application,
                        "context": c.context,
                        "duration_minutes": round((c.duration_seconds or 0) / 60, 1),
                    }
                    for c in comms
                ],
                "stats": {
                    "total_keystrokes": total_keys,
                    "active_minutes": active_minutes,
                    "total_app_minutes": round(total_app_seconds / 60, 1),
                    "app_count": len(apps),
                    "screenshot_count": len(screenshots),
                    "communication_sessions": len(comms),
                },
            }
        finally:
            session.close()

    def get_timeline_for_date(self, date: str) -> list[dict]:
        """Get a chronological timeline of all events for a given date."""
        session = self.db.get_session()
        try:
            day_start = datetime.strptime(date, "%Y-%m-%d")
            day_end = day_start + timedelta(days=1)

            events = []

            # App switches
            app_records = (
                session.query(ApplicationUsage)
                .filter(
                    ApplicationUsage.timestamp >= day_start,
                    ApplicationUsage.timestamp < day_end,
                )
                .order_by(ApplicationUsage.timestamp)
                .all()
            )
            for a in app_records:
                events.append(
                    {
                        "timestamp": a.timestamp.isoformat(),
                        "type": "app",
                        "title": a.application_name,
                        "detail": a.window_title,
                        "category": a.category,
                        "duration_minutes": round(
                            (a.duration_seconds or 0) / 60, 1
                        ),
                    }
                )

            # Screenshots
            ss_records = (
                session.query(Screenshot)
                .filter(
                    Screenshot.timestamp >= day_start,
                    Screenshot.timestamp < day_end,
                )
                .order_by(Screenshot.timestamp)
                .all()
            )
            for s in ss_records:
                events.append(
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "type": "screenshot",
                        "title": "Screenshot",
                        "detail": s.active_window_title,
                        "file_path": s.file_path,
                    }
                )

            # Communications
            comm_records = (
                session.query(CommunicationEvent)
                .filter(
                    CommunicationEvent.timestamp >= day_start,
                    CommunicationEvent.timestamp < day_end,
                )
                .order_by(CommunicationEvent.timestamp)
                .all()
            )
            for c in comm_records:
                events.append(
                    {
                        "timestamp": c.timestamp.isoformat(),
                        "type": "communication",
                        "title": c.application,
                        "detail": c.context,
                        "duration_minutes": round(
                            (c.duration_seconds or 0) / 60, 1
                        ),
                    }
                )

            events.sort(key=lambda e: e["timestamp"])
            return events
        finally:
            session.close()

    def get_summary(self, date: str) -> dict | None:
        """Get a stored daily summary."""
        session = self.db.get_session()
        try:
            summary = (
                session.query(DailySummary)
                .filter(DailySummary.date == date)
                .first()
            )
            if not summary:
                return None
            return {
                "date": summary.date,
                "generated_at": summary.generated_at.isoformat(),
                "summary": summary.summary_text,
                "conversations": summary.conversations_text,
                "plan": summary.plan_text,
                "stats": {
                    "total_active_minutes": summary.total_active_minutes,
                    "total_keystrokes": summary.total_keystrokes,
                    "top_applications": json.loads(summary.top_applications or "[]"),
                },
            }
        finally:
            session.close()

    def save_summary(self, date: str, summary: dict):
        """Save or update a daily summary."""
        session = self.db.get_session()
        try:
            existing = (
                session.query(DailySummary)
                .filter(DailySummary.date == date)
                .first()
            )
            if existing:
                existing.summary_text = summary.get("summary", "")
                existing.conversations_text = summary.get("conversations", "")
                existing.plan_text = summary.get("plan", "")
                existing.total_active_minutes = summary.get("active_minutes", 0)
                existing.total_keystrokes = summary.get("total_keystrokes", 0)
                existing.top_applications = json.dumps(
                    summary.get("top_applications", [])
                )
                existing.generated_at = datetime.utcnow()
            else:
                record = DailySummary(
                    date=date,
                    summary_text=summary.get("summary", ""),
                    conversations_text=summary.get("conversations", ""),
                    plan_text=summary.get("plan", ""),
                    total_active_minutes=summary.get("active_minutes", 0),
                    total_keystrokes=summary.get("total_keystrokes", 0),
                    top_applications=json.dumps(
                        summary.get("top_applications", [])
                    ),
                )
                session.add(record)
            session.commit()
        finally:
            session.close()

    def get_recent_dates_with_data(self, limit: int = 30) -> list[str]:
        """Get the most recent dates that have activity data."""
        session = self.db.get_session()
        try:
            dates = set()

            app_dates = (
                session.query(
                    func.date(ApplicationUsage.timestamp).label("d")
                )
                .distinct()
                .order_by(func.date(ApplicationUsage.timestamp).desc())
                .limit(limit)
                .all()
            )
            dates.update(row.d for row in app_dates if row.d)

            kb_dates = (
                session.query(
                    func.date(KeyboardActivity.timestamp).label("d")
                )
                .distinct()
                .order_by(func.date(KeyboardActivity.timestamp).desc())
                .limit(limit)
                .all()
            )
            dates.update(row.d for row in kb_dates if row.d)

            return sorted(dates, reverse=True)[:limit]
        finally:
            session.close()
