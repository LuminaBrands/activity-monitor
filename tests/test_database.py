"""Tests for the database layer."""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from activity_monitor.storage.models import (
    ApplicationUsage,
    CommunicationEvent,
    Database,
    KeyboardActivity,
    Screenshot,
)
from activity_monitor.database import ActivityDatabase


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def db(db_path):
    return Database(db_path)


@pytest.fixture
def activity_db(db_path):
    # Ensure tables are created
    Database(db_path)
    return ActivityDatabase(db_path)


class TestDatabaseSetup:
    def test_creates_tables(self, db):
        session = db.get_session()
        # Verify we can query all tables without error
        session.query(KeyboardActivity).all()
        session.query(ApplicationUsage).all()
        session.query(Screenshot).all()
        session.query(CommunicationEvent).all()
        session.close()


class TestKeyboardActivity:
    def test_insert_and_query(self, db):
        session = db.get_session()
        record = KeyboardActivity(
            application="VSCode",
            window_title="main.py - project",
            key_count=42,
            minute_bucket="2026-03-03 14:30",
        )
        session.add(record)
        session.commit()

        result = session.query(KeyboardActivity).first()
        assert result.application == "VSCode"
        assert result.key_count == 42
        assert result.minute_bucket == "2026-03-03 14:30"
        session.close()


class TestApplicationUsage:
    def test_insert_and_query(self, db):
        session = db.get_session()
        record = ApplicationUsage(
            application_name="Google Chrome",
            window_title="GitHub - Pull Requests",
            duration_seconds=300.5,
            category="browsing",
        )
        session.add(record)
        session.commit()

        result = session.query(ApplicationUsage).first()
        assert result.application_name == "Google Chrome"
        assert result.duration_seconds == 300.5
        assert result.category == "browsing"
        session.close()


class TestActivityDatabase:
    def test_get_activity_for_date_empty(self, activity_db):
        data = activity_db.get_activity_for_date("2026-03-03")
        assert data["date"] == "2026-03-03"
        assert data["keyboard"] == []
        assert data["applications"] == []
        assert data["stats"]["total_keystrokes"] == 0

    def test_get_activity_for_date_with_data(self, activity_db):
        session = activity_db.get_session()
        now = datetime(2026, 3, 3, 14, 0, 0)

        session.add(
            KeyboardActivity(
                timestamp=now,
                application="VSCode",
                window_title="test.py",
                key_count=100,
                minute_bucket="2026-03-03 14:00",
            )
        )
        session.add(
            ApplicationUsage(
                timestamp=now,
                application_name="VSCode",
                window_title="test.py",
                duration_seconds=600,
                category="coding",
            )
        )
        session.add(
            CommunicationEvent(
                timestamp=now,
                application="Slack",
                window_title="#general - Workspace",
                duration_seconds=120,
                context="#general",
            )
        )
        session.commit()
        session.close()

        data = activity_db.get_activity_for_date("2026-03-03")
        assert data["stats"]["total_keystrokes"] == 100
        assert data["stats"]["active_minutes"] == 1
        assert data["stats"]["app_count"] == 1
        assert data["stats"]["communication_sessions"] == 1
        assert len(data["applications"]) == 1
        assert data["applications"][0]["name"] == "VSCode"

    def test_save_and_get_summary(self, activity_db):
        activity_db.save_summary(
            "2026-03-03",
            {
                "summary": "Worked on the project.",
                "conversations": "Chatted in Slack.",
                "plan": "Continue tomorrow.",
                "active_minutes": 120,
                "total_keystrokes": 5000,
                "top_applications": ["VSCode", "Chrome"],
            },
        )

        result = activity_db.get_summary("2026-03-03")
        assert result is not None
        assert result["date"] == "2026-03-03"
        assert "Worked on the project" in result["summary"]
        assert result["stats"]["total_active_minutes"] == 120

    def test_get_summary_nonexistent(self, activity_db):
        result = activity_db.get_summary("2000-01-01")
        assert result is None

    def test_get_timeline_for_date(self, activity_db):
        session = activity_db.get_session()
        now = datetime(2026, 3, 3, 10, 0, 0)

        session.add(
            ApplicationUsage(
                timestamp=now,
                application_name="Terminal",
                window_title="bash",
                duration_seconds=300,
                category="coding",
            )
        )
        session.add(
            ApplicationUsage(
                timestamp=now + timedelta(minutes=10),
                application_name="Chrome",
                window_title="Google",
                duration_seconds=120,
                category="browsing",
            )
        )
        session.commit()
        session.close()

        timeline = activity_db.get_timeline_for_date("2026-03-03")
        assert len(timeline) == 2
        assert timeline[0]["title"] == "Terminal"
        assert timeline[1]["title"] == "Chrome"
        # Verify chronological order
        assert timeline[0]["timestamp"] < timeline[1]["timestamp"]
