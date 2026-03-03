"""Activity Monitor - Main entry point and CLI."""

import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import click

from activity_monitor.config import load_config
from activity_monitor.database import ActivityDatabase
from activity_monitor.storage.models import Database


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("activity-monitor")


@click.group()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.pass_context
def cli(ctx, config):
    """Activity Monitor - Track your daily computer activity."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.pass_context
def start(ctx):
    """Start monitoring and the web dashboard."""
    config = ctx.obj["config"]

    # Ensure data directories exist
    db_path = config["storage"]["database_path"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    ss_path = config["monitoring"]["screenshots"]["storage_path"]
    Path(ss_path).mkdir(parents=True, exist_ok=True)

    # Initialize database
    db = Database(db_path)
    session_factory = db.get_session

    monitors = []

    # Start keyboard monitor
    kb_monitor = None
    if config["monitoring"]["keyboard"]["enabled"]:
        from activity_monitor.monitors.keyboard import KeyboardMonitor

        kb_monitor = KeyboardMonitor(config, session_factory)
        monitors.append(kb_monitor)
        logger.info("Keyboard monitoring enabled")

    # Start application monitor
    if config["monitoring"]["applications"]["enabled"]:
        from activity_monitor.monitors.application import ApplicationMonitor

        app_monitor = ApplicationMonitor(config, session_factory, kb_monitor)
        monitors.append(app_monitor)
        logger.info("Application monitoring enabled")

    # Start screenshot monitor
    if config["monitoring"]["screenshots"]["enabled"]:
        from activity_monitor.monitors.screenshot import ScreenshotMonitor

        ss_monitor = ScreenshotMonitor(config, session_factory)
        monitors.append(ss_monitor)
        logger.info("Screenshot monitoring enabled (every %ds)", config["monitoring"]["screenshots"]["interval_seconds"])

    # Start communication monitor
    if config["monitoring"]["communications"]["enabled"]:
        from activity_monitor.monitors.communication import CommunicationMonitor

        comm_monitor = CommunicationMonitor(config, session_factory)
        monitors.append(comm_monitor)
        logger.info("Communication monitoring enabled")

    # Start all monitors
    for monitor in monitors:
        monitor.start()

    logger.info("All monitors started. %d active.", len(monitors))

    # Handle graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down monitors...")
        for monitor in monitors:
            monitor.stop()
        logger.info("All monitors stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start web dashboard
    host = config["dashboard"]["host"]
    port = config["dashboard"]["port"]
    logger.info("Starting dashboard at http://%s:%d", host, port)

    from activity_monitor.app import create_app

    app = create_app(config)
    app.run(host=host, port=port, debug=False, use_reloader=False)


@cli.command()
@click.pass_context
def dashboard(ctx):
    """Start only the web dashboard (no monitoring)."""
    config = ctx.obj["config"]

    db_path = config["storage"]["database_path"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    host = config["dashboard"]["host"]
    port = config["dashboard"]["port"]

    logger.info("Starting dashboard at http://%s:%d", host, port)

    from activity_monitor.app import create_app

    app = create_app(config)
    app.run(host=host, port=port, debug=True)


@cli.command()
@click.option("--date", "-d", default=None, help="Date to summarize (YYYY-MM-DD)")
@click.pass_context
def summarize(ctx, date):
    """Generate an AI summary for a given day."""
    config = ctx.obj["config"]

    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    db_path = config["storage"]["database_path"]
    if not Path(db_path).exists():
        click.echo("No activity database found. Run 'start' first to begin monitoring.")
        return

    activity_db = ActivityDatabase(db_path)

    from activity_monitor.analysis.summarizer import ActivitySummarizer

    summarizer = ActivitySummarizer(config, activity_db)

    click.echo(f"Generating summary for {date}...")
    try:
        result = summarizer.generate_summary(date)
        click.echo("\n" + "=" * 60)
        click.echo(f"  DAILY SUMMARY - {date}")
        click.echo("=" * 60 + "\n")
        click.echo(result["summary"])
    except ValueError as e:
        click.echo(f"Error: {e}")
    except Exception as e:
        click.echo(f"Failed to generate summary: {e}")


@cli.command()
@click.option("--days", "-d", default=3, help="Number of days to plan ahead")
@click.pass_context
def plan(ctx, days):
    """Generate a forward-looking plan based on recent activity."""
    config = ctx.obj["config"]

    db_path = config["storage"]["database_path"]
    if not Path(db_path).exists():
        click.echo("No activity database found. Run 'start' first to begin monitoring.")
        return

    activity_db = ActivityDatabase(db_path)

    from activity_monitor.analysis.summarizer import ActivitySummarizer

    summarizer = ActivitySummarizer(config, activity_db)

    click.echo(f"Generating plan for the next {days} days...")
    try:
        result = summarizer.generate_plan(planning_days=days)
        click.echo("\n" + "=" * 60)
        click.echo(f"  PLAN - Next {days} Days")
        click.echo("=" * 60 + "\n")
        click.echo(result)
    except ValueError as e:
        click.echo(f"Error: {e}")
    except Exception as e:
        click.echo(f"Failed to generate plan: {e}")


@cli.command()
@click.option("--date", "-d", default=None, help="Date to view (YYYY-MM-DD)")
@click.pass_context
def status(ctx, date):
    """Show activity stats for a given day."""
    config = ctx.obj["config"]

    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    db_path = config["storage"]["database_path"]
    if not Path(db_path).exists():
        click.echo("No activity database found. Run 'start' first.")
        return

    activity_db = ActivityDatabase(db_path)
    data = activity_db.get_activity_for_date(date)
    stats = data["stats"]

    click.echo(f"\nActivity for {date}:")
    click.echo(f"  Active minutes:   {stats['active_minutes']}")
    click.echo(f"  Keystrokes:       {stats['total_keystrokes']:,}")
    click.echo(f"  Applications:     {stats['app_count']}")
    click.echo(f"  Screenshots:      {stats['screenshot_count']}")
    click.echo(f"  Comm. sessions:   {stats['communication_sessions']}")

    if data["applications"]:
        click.echo(f"\nTop applications:")
        for app in data["applications"][:5]:
            click.echo(f"  {app['name']:30s} {app['total_minutes']:>6.1f} min  ({app['category']})")

    if data["communications"]:
        click.echo(f"\nConversations:")
        for c in data["communications"][:5]:
            click.echo(f"  [{c['timestamp'][:16]}] {c['application']}: {c['context']}")


if __name__ == "__main__":
    cli()
