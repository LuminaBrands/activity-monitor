"""Configuration management for Activity Monitor."""

import os
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
LOCAL_CONFIG_PATH = Path(__file__).parent.parent / "config.local.yaml"


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML files and environment variables.

    Priority: env vars > config.local.yaml > config.yaml
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    with open(path) as f:
        config = yaml.safe_load(f)

    # Overlay local config if it exists
    if LOCAL_CONFIG_PATH.exists():
        with open(LOCAL_CONFIG_PATH) as f:
            local = yaml.safe_load(f) or {}
        config = _deep_merge(config, local)

    # Environment variable overrides
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        config["analysis"]["anthropic_api_key"] = api_key

    # Resolve relative paths to absolute
    base_dir = Path(config_path).parent if config_path else DEFAULT_CONFIG_PATH.parent
    config["storage"]["database_path"] = str(
        base_dir / config["storage"]["database_path"]
    )
    config["monitoring"]["screenshots"]["storage_path"] = str(
        base_dir / config["monitoring"]["screenshots"]["storage_path"]
    )

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
