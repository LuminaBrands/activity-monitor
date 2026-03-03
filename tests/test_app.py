"""Tests for the Flask web application."""

import os
import tempfile

import pytest

from activity_monitor.app import create_app
from activity_monitor.config import load_config


@pytest.fixture
def app():
    config = load_config()
    # Use temp database for tests
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    config["storage"]["database_path"] = db_path
    app = create_app(config)
    app.config["TESTING"] = True
    yield app
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


class TestDashboardRoutes:
    def test_index(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"Activity Monitor" in response.data

    def test_timeline(self, client):
        response = client.get("/timeline")
        assert response.status_code == 200

    def test_summary(self, client):
        response = client.get("/summary")
        assert response.status_code == 200


class TestAPIRoutes:
    def test_get_activity(self, client):
        response = client.get("/api/activity/2026-03-03")
        assert response.status_code == 200
        data = response.get_json()
        assert data["date"] == "2026-03-03"
        assert "stats" in data

    def test_get_timeline(self, client):
        response = client.get("/api/timeline/2026-03-03")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_get_summary_empty(self, client):
        response = client.get("/api/summary/2026-03-03")
        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] is None

    def test_get_dates(self, client):
        response = client.get("/api/dates")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
