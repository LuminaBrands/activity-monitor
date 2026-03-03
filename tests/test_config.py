"""Tests for configuration loading."""

import os
import tempfile

import pytest
import yaml

from activity_monitor.config import load_config, _deep_merge


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_base_unchanged(self):
        base = {"a": 1}
        override = {"a": 2}
        _deep_merge(base, override)
        assert base == {"a": 1}


class TestLoadConfig:
    def test_loads_default_config(self):
        config = load_config()
        assert "monitoring" in config
        assert "analysis" in config
        assert "dashboard" in config
        assert "storage" in config

    def test_keyboard_config(self):
        config = load_config()
        assert config["monitoring"]["keyboard"]["enabled"] is True

    def test_screenshot_config(self):
        config = load_config()
        ss = config["monitoring"]["screenshots"]
        assert ss["enabled"] is True
        assert ss["interval_seconds"] == 300
        assert ss["quality"] == 50

    def test_dashboard_config(self):
        config = load_config()
        assert config["dashboard"]["host"] == "127.0.0.1"
        assert config["dashboard"]["port"] == 5050

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
        config = load_config()
        assert config["analysis"]["anthropic_api_key"] == "test-key-123"
