"""Tests for monitor modules."""

import pytest

from activity_monitor.monitors.application import _categorize_app
from activity_monitor.monitors.communication import _extract_context


class TestCategorizeApp:
    def test_coding_apps(self):
        assert _categorize_app("Visual Studio Code") == "coding"
        assert _categorize_app("PyCharm") == "coding"
        assert _categorize_app("Terminal") == "coding"
        assert _categorize_app("iTerm2") == "coding"
        assert _categorize_app("Cursor") == "coding"

    def test_browsing_apps(self):
        assert _categorize_app("Google Chrome") == "browsing"
        assert _categorize_app("Firefox") == "browsing"
        assert _categorize_app("Safari") == "browsing"
        assert _categorize_app("Arc") == "browsing"

    def test_communication_apps(self):
        assert _categorize_app("Slack") == "communication"
        assert _categorize_app("Discord") == "communication"
        assert _categorize_app("Microsoft Teams") == "communication"
        assert _categorize_app("Zoom") == "communication"
        assert _categorize_app("Microsoft Outlook") == "communication"

    def test_design_apps(self):
        assert _categorize_app("Figma") == "design"
        assert _categorize_app("Sketch") == "design"

    def test_document_apps(self):
        assert _categorize_app("Microsoft Word") == "documents"
        assert _categorize_app("Notion") == "documents"
        assert _categorize_app("Obsidian") == "documents"

    def test_unknown_app(self):
        assert _categorize_app("SomeRandomApp") == "other"


class TestExtractContext:
    def test_slack_context(self):
        assert _extract_context("Slack", "#engineering - Acme Corp") == "#engineering"
        assert _extract_context("Slack", "John Smith - Acme Corp") == "John Smith"

    def test_teams_context(self):
        assert _extract_context("Microsoft Teams", "General | Microsoft Teams") == "General"

    def test_discord_context(self):
        assert _extract_context("Discord", "#dev-chat - My Server") == "#dev-chat"

    def test_email_context(self):
        assert _extract_context("Outlook", "Re: Q4 Budget - Microsoft Outlook") == "Re: Q4 Budget"
        assert _extract_context("Mail", "Inbox - user@example.com - Mail") == "Inbox"

    def test_empty_context(self):
        assert _extract_context("Slack", "") == ""

    def test_unknown_app_context(self):
        result = _extract_context("UnknownApp", "Some Window Title Here")
        assert result == "Some Window Title Here"
