"""Flask web dashboard for Activity Monitor."""

import os
import platform
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request, send_from_directory

from activity_monitor.config import load_config, LOCAL_CONFIG_PATH
from activity_monitor.database import ActivityDatabase
from activity_monitor.analysis.summarizer import ActivitySummarizer


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    if config is None:
        config = load_config()

    app.config["ACTIVITY_CONFIG"] = config
    db = ActivityDatabase(config["storage"]["database_path"])
    summarizer = ActivitySummarizer(config, db)

    @app.route("/")
    def dashboard():
        today = datetime.utcnow().strftime("%Y-%m-%d")
        dates = db.get_recent_dates_with_data(limit=30)
        return render_template("dashboard.html", today=today, dates=dates)

    @app.route("/timeline")
    def timeline():
        date = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        return render_template("timeline.html", date=date)

    @app.route("/chat-history")
    def chat_history():
        date = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        return render_template("chat-history.html", date=date)

    @app.route("/summary")
    def summary():
        date = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        return render_template("summary.html", date=date)

    # --- API endpoints ---

    @app.route("/api/activity/<date>")
    def api_activity(date):
        data = db.get_activity_for_date(date)
        return jsonify(data)

    @app.route("/api/timeline/<date>")
    def api_timeline(date):
        events = db.get_timeline_for_date(date)
        return jsonify(events)

    @app.route("/api/chat-history/<date>")
    def api_chat_history(date):
        activity = db.get_activity_for_date(date)
        comms = activity["communications"]

        # Aggregate by application
        by_app: dict[str, dict] = {}
        for c in comms:
            app_name = c["application"]
            if app_name not in by_app:
                by_app[app_name] = {"name": app_name, "sessions": 0, "total_minutes": 0}
            by_app[app_name]["sessions"] += 1
            by_app[app_name]["total_minutes"] = round(
                by_app[app_name]["total_minutes"] + c["duration_minutes"], 1
            )

        apps_summary = sorted(by_app.values(), key=lambda a: -a["total_minutes"])
        total_minutes = round(sum(c["duration_minutes"] for c in comms), 1)
        unique_apps = len(by_app)

        # Get conversations recap from stored summary
        stored = db.get_summary(date)
        conversations_recap = None
        if stored and stored.get("conversations"):
            conversations_recap = stored["conversations"]

        return jsonify({
            "date": date,
            "communications": comms,
            "by_app": apps_summary,
            "conversations_recap": conversations_recap,
            "stats": {
                "total_sessions": len(comms),
                "total_minutes": total_minutes,
                "unique_apps": unique_apps,
            },
        })

    @app.route("/api/summary/<date>")
    def api_summary(date):
        stored = db.get_summary(date)
        if stored:
            return jsonify(stored)
        return jsonify({"date": date, "summary": None})

    @app.route("/api/generate-summary/<date>", methods=["POST"])
    def api_generate_summary(date):
        try:
            result = summarizer.generate_summary(date)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to generate summary: {e}"}), 500

    @app.route("/api/generate-plan", methods=["POST"])
    def api_generate_plan():
        try:
            days = request.json.get("days", 3) if request.is_json else 3
            plan = summarizer.generate_plan(planning_days=days)
            return jsonify({"plan": plan})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to generate plan: {e}"}), 500

    @app.route("/api/dates")
    def api_dates():
        dates = db.get_recent_dates_with_data(limit=30)
        return jsonify(dates)

    @app.route("/settings")
    def settings():
        return render_template("settings.html")

    @app.route("/api/config", methods=["GET"])
    def api_get_config():
        """Return current configuration (masking API key)."""
        safe_config = {
            "monitoring": config["monitoring"],
            "analysis": {
                "anthropic_api_key_set": bool(config["analysis"].get("anthropic_api_key")),
                "model": config["analysis"].get("model", "claude-sonnet-4-6"),
                "auto_summary_time": config["analysis"].get("auto_summary_time", "17:30"),
                "planning_days": config["analysis"].get("planning_days", 3),
            },
            "dashboard": config["dashboard"],
            "storage": {
                "database_path": config["storage"]["database_path"],
            },
        }
        return jsonify(safe_config)

    @app.route("/api/config", methods=["POST"])
    def api_save_config():
        """Save configuration changes to config.local.yaml."""
        updates = request.json
        if not updates:
            return jsonify({"error": "No configuration provided"}), 400

        # Load existing local config or start fresh
        local_config = {}
        if LOCAL_CONFIG_PATH.exists():
            with open(LOCAL_CONFIG_PATH) as f:
                local_config = yaml.safe_load(f) or {}

        # Apply updates
        if "monitoring" in updates:
            if "monitoring" not in local_config:
                local_config["monitoring"] = {}
            mon = updates["monitoring"]
            if "keyboard" in mon:
                local_config["monitoring"]["keyboard"] = {
                    "enabled": bool(mon["keyboard"].get("enabled", True))
                }
            if "applications" in mon:
                local_config["monitoring"]["applications"] = {
                    "enabled": bool(mon["applications"].get("enabled", True)),
                    "poll_interval_seconds": int(
                        mon["applications"].get("poll_interval_seconds", 5)
                    ),
                }
            if "screenshots" in mon:
                local_config["monitoring"]["screenshots"] = {
                    "enabled": bool(mon["screenshots"].get("enabled", True)),
                    "interval_seconds": int(
                        mon["screenshots"].get("interval_seconds", 300)
                    ),
                    "quality": int(mon["screenshots"].get("quality", 50)),
                    "max_storage_gb": int(
                        mon["screenshots"].get("max_storage_gb", 5)
                    ),
                }
            if "communications" in mon:
                local_config["monitoring"]["communications"] = {
                    "enabled": bool(
                        mon["communications"].get("enabled", True)
                    )
                }
        if "analysis" in updates:
            if "analysis" not in local_config:
                local_config["analysis"] = {}
            analysis = updates["analysis"]
            if "anthropic_api_key" in analysis and analysis["anthropic_api_key"]:
                local_config["analysis"]["anthropic_api_key"] = analysis[
                    "anthropic_api_key"
                ]
            if "model" in analysis:
                local_config["analysis"]["model"] = analysis["model"]

        with open(LOCAL_CONFIG_PATH, "w") as f:
            yaml.dump(local_config, f, default_flow_style=False, sort_keys=False)

        # Update in-memory config
        for key in local_config:
            if isinstance(local_config[key], dict) and key in config:
                for subkey in local_config[key]:
                    if isinstance(local_config[key][subkey], dict):
                        if subkey not in config[key]:
                            config[key][subkey] = {}
                        config[key][subkey].update(local_config[key][subkey])
                    else:
                        config[key][subkey] = local_config[key][subkey]

        return jsonify({"status": "saved"})

    @app.route("/api/setup-status")
    def api_setup_status():
        """Check what's configured and what permissions might be needed."""
        system = platform.system()

        # Check tool availability
        has_xdotool = shutil.which("xdotool") is not None
        has_gdbus = shutil.which("gdbus") is not None

        permissions = []

        if system == "Darwin":
            permissions = [
                {
                    "name": "Accessibility Access",
                    "description": "Required for keyboard monitoring and active window detection",
                    "how": "System Settings > Privacy & Security > Accessibility > Enable for Activity Monitor / Terminal",
                    "required_for": ["keyboard", "applications"],
                },
                {
                    "name": "Screen Recording",
                    "description": "Required for capturing screenshots",
                    "how": "System Settings > Privacy & Security > Screen Recording > Enable for Activity Monitor / Terminal",
                    "required_for": ["screenshots"],
                },
                {
                    "name": "Input Monitoring",
                    "description": "Required for keyboard activity tracking",
                    "how": "System Settings > Privacy & Security > Input Monitoring > Enable for Activity Monitor / Terminal",
                    "required_for": ["keyboard"],
                },
            ]
        elif system == "Linux":
            permissions = [
                {
                    "name": "Display Server Access",
                    "description": "xdotool (X11) or gdbus (Wayland/GNOME) for window detection",
                    "how": "Install xdotool: sudo apt install xdotool (X11) or use GNOME on Wayland",
                    "required_for": ["applications", "communications"],
                    "satisfied": has_xdotool or has_gdbus,
                },
                {
                    "name": "Input Group Membership",
                    "description": "Your user must be in the 'input' group for keyboard monitoring",
                    "how": "sudo usermod -aG input $USER (then log out and back in)",
                    "required_for": ["keyboard"],
                },
                {
                    "name": "Screenshot Tools",
                    "description": "mss library for screen capture (works on X11 and most Wayland compositors)",
                    "how": "pip install mss Pillow",
                    "required_for": ["screenshots"],
                },
            ]
        elif system == "Windows":
            permissions = [
                {
                    "name": "Run as User",
                    "description": "No special permissions needed for most features on Windows",
                    "how": "Just run the application normally",
                    "required_for": ["keyboard", "applications", "screenshots"],
                },
            ]

        api_key_set = bool(config["analysis"].get("anthropic_api_key"))
        db_exists = Path(config["storage"]["database_path"]).exists()

        return jsonify({
            "platform": system,
            "permissions": permissions,
            "api_key_configured": api_key_set,
            "database_exists": db_exists,
            "monitors": {
                "keyboard": config["monitoring"]["keyboard"]["enabled"],
                "applications": config["monitoring"]["applications"]["enabled"],
                "screenshots": config["monitoring"]["screenshots"]["enabled"],
                "communications": config["monitoring"]["communications"]["enabled"],
            },
        })

    @app.route("/screenshots/<path:filepath>")
    def serve_screenshot(filepath):
        screenshots_dir = config["monitoring"]["screenshots"]["storage_path"]
        return send_from_directory(screenshots_dir, filepath)

    return app
