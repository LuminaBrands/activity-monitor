# Activity Monitor

Track your daily computer activity and generate AI-powered summaries of what you worked on.

## Features

- **Keyboard Tracking** — Monitors typing activity volume per application (no raw keystrokes logged by default for privacy)
- **Application Tracking** — Records which apps and windows you use and for how long, with automatic categorization (coding, browsing, communication, etc.)
- **Screenshot Capture** — Periodic screenshots with configurable interval and quality, auto-rotated to respect storage limits
- **Communication Detection** — Tracks when you're in Slack, Teams, Discord, email, etc., and extracts context from window titles (channel names, email subjects)
- **AI Daily Summaries** — Uses Claude to generate detailed narratives of your workday, including what you worked on, conversations you had, and key highlights
- **AI Planning** — Generates a plan for the next few days based on your recent activity patterns
- **Web Dashboard** — Dark-themed dashboard with stats, timelines, screenshot galleries, and one-click AI summary generation

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key (for AI summaries)
export ANTHROPIC_API_KEY="your-key-here"

# Start monitoring + dashboard
python main.py start
```

Then open http://127.0.0.1:5050 in your browser.

## CLI Commands

```bash
# Start full monitoring + web dashboard
python main.py start

# Start only the web dashboard (view historical data)
python main.py dashboard

# Generate an AI summary for today
python main.py summarize

# Generate a summary for a specific date
python main.py summarize --date 2026-03-01

# Generate a plan for the next 3 days
python main.py plan

# View quick stats for today
python main.py status
```

## Configuration

Edit `config.yaml` to customize monitoring behavior. For secrets (API keys), create a `config.local.yaml` that won't be committed:

```yaml
# config.local.yaml
analysis:
  anthropic_api_key: "sk-ant-..."
```

### Key Settings

| Setting | Default | Description |
|---|---|---|
| `monitoring.keyboard.enabled` | `true` | Track typing activity |
| `monitoring.screenshots.interval_seconds` | `300` | Screenshot frequency (5 min) |
| `monitoring.screenshots.quality` | `50` | JPEG quality (1-100) |
| `monitoring.screenshots.max_storage_gb` | `5` | Auto-delete oldest when exceeded |
| `dashboard.port` | `5050` | Web dashboard port |
| `analysis.model` | `claude-sonnet-4-6` | Claude model for summaries |

## Architecture

```
activity_monitor/
├── monitors/          # Data collection
│   ├── keyboard.py    # Typing activity tracking
│   ├── application.py # Active app/window polling
│   ├── screenshot.py  # Periodic screen capture
│   └── communication.py # Comm app detection
├── analysis/
│   └── summarizer.py  # AI summary + plan generation
├── storage/
│   └── models.py      # SQLAlchemy models + DB setup
├── database.py        # High-level query interface
├── config.py          # YAML config loading
├── app.py             # Flask web dashboard
├── templates/         # HTML templates
└── static/            # CSS + JavaScript
```

## Privacy

- By default, **raw keystrokes are NOT logged** — only the count per minute per application
- All data is stored locally in SQLite (`data/activity_monitor.db`)
- Screenshots stay on your machine in the `screenshots/` directory
- AI summaries are generated via API calls to Anthropic — activity data is sent to generate summaries
- No data is sent anywhere else

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Platform Support

| Feature | macOS | Linux (X11) | Linux (Wayland) | Windows |
|---|---|---|---|---|
| Keyboard tracking | Yes | Yes | Partial | Yes |
| App/window tracking | Yes | Yes | Partial (GNOME) | Yes |
| Screenshots | Yes | Yes | Yes | Yes |
| Communication detection | Yes | Yes | Yes | Yes |
