"""Flask web dashboard for Activity Monitor."""

import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, send_from_directory

from activity_monitor.config import load_config
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

    @app.route("/screenshots/<path:filepath>")
    def serve_screenshot(filepath):
        screenshots_dir = config["monitoring"]["screenshots"]["storage_path"]
        return send_from_directory(screenshots_dir, filepath)

    return app
