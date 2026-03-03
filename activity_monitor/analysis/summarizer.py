"""AI-powered daily activity summarizer using Claude."""

import json
import logging
from datetime import datetime

import anthropic

from activity_monitor.database import ActivityDatabase

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """\
You are an executive assistant helping a busy professional recall their daily \
computer activity. You receive structured data about their application usage, \
keyboard activity, screenshots, and communication sessions.

Your job is to produce a clear, actionable daily summary that helps them:
1. Recall exactly what they worked on and when
2. Remember conversations they had (Slack, email, meetings)
3. Understand how they spent their time

Be specific and concrete. Use timestamps. Group related activities together. \
Highlight important-seeming conversations and context switches."""

SUMMARY_USER_TEMPLATE = """\
Here is my computer activity data for {date}:

## Application Usage
{app_usage}

## Keyboard Activity (typing volume by app)
{keyboard_summary}

## Communication Sessions
{comm_sessions}

## Screenshots Timeline
{screenshots_summary}

## Overall Stats
- Total active typing minutes: {active_minutes}
- Total keystrokes: {total_keystrokes}
- Applications used: {app_count}
- Communication sessions: {comm_count}

---

Please generate:

### 1. Daily Summary
A detailed narrative of what I worked on today, organized chronologically. \
Include specific applications, window titles, and approximate time spent. \
Be specific about what I was likely doing based on the app + window context.

### 2. Conversations & Communications
A recap of all my communication activity — which apps I used, which \
channels/people/subjects I interacted with (based on window titles), \
and approximate duration of each.

### 3. Key Highlights
The 3-5 most notable things from my day (big tasks completed, long meetings, \
intense coding sessions, etc.)."""

PLAN_SYSTEM_PROMPT = """\
You are a productivity assistant. Based on the user's recent activity patterns \
and today's summary, suggest a practical plan for the next few days. \
Consider work patterns, unfinished tasks, and communication follow-ups."""

PLAN_USER_TEMPLATE = """\
Here is my activity summary for the past few days:

{recent_summaries}

Based on these patterns, create a plan for the next {planning_days} days that:
1. Identifies tasks that seem unfinished or ongoing
2. Suggests follow-ups for conversations/communications
3. Notes patterns (e.g., "you tend to context-switch a lot in afternoons")
4. Recommends a prioritized task list for each upcoming day

Keep it practical and actionable."""


def _format_app_usage(apps: list[dict]) -> str:
    if not apps:
        return "No application data recorded."
    lines = []
    for app in apps:
        lines.append(
            f"- {app['name']} ({app['category']}): "
            f"{app['total_minutes']} min across {app['sessions']} sessions"
        )
    return "\n".join(lines)


def _format_keyboard_summary(keyboard_data: list[dict]) -> str:
    if not keyboard_data:
        return "No keyboard data recorded."
    # Aggregate by application
    by_app: dict[str, int] = {}
    for entry in keyboard_data:
        app = entry.get("application", "Unknown")
        by_app[app] = by_app.get(app, 0) + entry.get("key_count", 0)

    lines = []
    for app, count in sorted(by_app.items(), key=lambda x: -x[1]):
        lines.append(f"- {app}: {count:,} keystrokes")
    return "\n".join(lines)


def _format_comm_sessions(comms: list[dict]) -> str:
    if not comms:
        return "No communication sessions recorded."
    lines = []
    for c in comms:
        lines.append(
            f"- [{c['timestamp'][:16]}] {c['application']}: "
            f"{c['context']} ({c['duration_minutes']} min)"
        )
    return "\n".join(lines)


def _format_screenshots(screenshots: list[dict]) -> str:
    if not screenshots:
        return "No screenshots captured."
    lines = []
    for s in screenshots:
        lines.append(
            f"- [{s['timestamp'][:16]}] {s['active_app']}: {s['window_title']}"
        )
    return "\n".join(lines)


class ActivitySummarizer:
    """Generates AI-powered summaries from activity data."""

    def __init__(self, config: dict, activity_db: ActivityDatabase):
        self.config = config
        self.db = activity_db
        analysis_config = config.get("analysis", {})
        self._api_key = analysis_config.get("anthropic_api_key", "")
        self._model = analysis_config.get("model", "claude-sonnet-4-6")

    def _get_client(self) -> anthropic.Anthropic:
        if not self._api_key:
            raise ValueError(
                "Anthropic API key not configured. Set ANTHROPIC_API_KEY "
                "env var or add it to config.local.yaml"
            )
        return anthropic.Anthropic(api_key=self._api_key)

    def generate_summary(self, date: str) -> dict:
        """Generate a daily summary for the given date.

        Returns dict with keys: summary, conversations, highlights.
        """
        activity = self.db.get_activity_for_date(date)
        stats = activity["stats"]

        if stats["total_keystrokes"] == 0 and stats["app_count"] == 0:
            return {
                "summary": "No activity recorded for this date.",
                "conversations": "No communication sessions recorded.",
                "highlights": "No data available.",
            }

        user_message = SUMMARY_USER_TEMPLATE.format(
            date=date,
            app_usage=_format_app_usage(activity["applications"]),
            keyboard_summary=_format_keyboard_summary(activity["keyboard"]),
            comm_sessions=_format_comm_sessions(activity["communications"]),
            screenshots_summary=_format_screenshots(activity["screenshots"]),
            active_minutes=stats["active_minutes"],
            total_keystrokes=stats["total_keystrokes"],
            app_count=stats["app_count"],
            comm_count=stats["communication_sessions"],
        )

        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = response.content[0].text

        # Store the summary
        self.db.save_summary(
            date,
            {
                "summary": result_text,
                "conversations": "",  # Included in main summary
                "plan": "",
                "active_minutes": stats["active_minutes"],
                "total_keystrokes": stats["total_keystrokes"],
                "top_applications": [
                    a["name"] for a in activity["applications"][:5]
                ],
            },
        )

        return {
            "summary": result_text,
            "stats": stats,
            "date": date,
        }

    def generate_plan(self, planning_days: int = 3) -> str:
        """Generate a forward-looking plan based on recent activity."""
        recent_dates = self.db.get_recent_dates_with_data(limit=7)

        summaries = []
        for date in recent_dates[:5]:
            stored = self.db.get_summary(date)
            if stored:
                summaries.append(f"## {date}\n{stored['summary']}")
            else:
                activity = self.db.get_activity_for_date(date)
                stats = activity["stats"]
                summaries.append(
                    f"## {date}\n"
                    f"Active minutes: {stats['active_minutes']}, "
                    f"Keystrokes: {stats['total_keystrokes']}, "
                    f"Apps: {stats['app_count']}"
                )

        if not summaries:
            return "Not enough activity data to generate a plan yet."

        user_message = PLAN_USER_TEMPLATE.format(
            recent_summaries="\n\n".join(summaries),
            planning_days=planning_days,
        )

        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=PLAN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text
