"""Active application and window tracker."""

import logging
import platform
import subprocess
import time
from datetime import datetime

from activity_monitor.monitors.base import BaseMonitor
from activity_monitor.storage.models import ApplicationUsage

logger = logging.getLogger(__name__)

# Heuristic category mapping
APP_CATEGORIES = {
    # Coding
    "code": "coding",
    "visual studio code": "coding",
    "vscode": "coding",
    "pycharm": "coding",
    "intellij": "coding",
    "webstorm": "coding",
    "sublime": "coding",
    "vim": "coding",
    "neovim": "coding",
    "terminal": "coding",
    "iterm": "coding",
    "warp": "coding",
    "alacritty": "coding",
    "kitty": "coding",
    "cursor": "coding",
    # Browsing
    "chrome": "browsing",
    "firefox": "browsing",
    "safari": "browsing",
    "brave": "browsing",
    "edge": "browsing",
    "arc": "browsing",
    # Communication
    "slack": "communication",
    "discord": "communication",
    "teams": "communication",
    "zoom": "communication",
    "meet": "communication",
    "outlook": "communication",
    "mail": "communication",
    "thunderbird": "communication",
    "messages": "communication",
    # Design
    "figma": "design",
    "sketch": "design",
    "photoshop": "design",
    "illustrator": "design",
    "canva": "design",
    # Documents
    "word": "documents",
    "docs": "documents",
    "pages": "documents",
    "notion": "documents",
    "obsidian": "documents",
    "excel": "documents",
    "sheets": "documents",
    "numbers": "documents",
    "powerpoint": "documents",
    "keynote": "documents",
}


def _categorize_app(app_name: str) -> str:
    """Guess a category from the application name."""
    lower = app_name.lower()
    for keyword, category in APP_CATEGORIES.items():
        if keyword in lower:
            return category
    return "other"


def get_active_window_info() -> tuple[str, str]:
    """Get the currently active application name and window title.

    Returns (application_name, window_title). Platform-specific.
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        try:
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
            end tell
            return frontApp
            '''
            app = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            app_name = app.stdout.strip()

            title_script = '''
            tell application "System Events"
                tell (first application process whose frontmost is true)
                    try
                        return name of front window
                    on error
                        return ""
                    end try
                end tell
            end tell
            '''
            title = subprocess.run(
                ["osascript", "-e", title_script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            window_title = title.stdout.strip()
            return (app_name, window_title)
        except Exception:
            return ("Unknown", "")

    elif system == "Linux":
        try:
            # Try xdotool (X11)
            wid = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if wid.returncode == 0:
                window_id = wid.stdout.strip()
                name_result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                window_title = name_result.stdout.strip()

                # Get the PID and then the process name
                pid_result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowpid"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if pid_result.returncode == 0 and pid_result.stdout.strip():
                    pid = pid_result.stdout.strip()
                    comm_result = subprocess.run(
                        ["ps", "-p", pid, "-o", "comm="],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    app_name = comm_result.stdout.strip()
                else:
                    app_name = window_title.split(" - ")[-1] if " - " in window_title else window_title

                return (app_name, window_title)
        except FileNotFoundError:
            pass

        try:
            # Fallback: try gdbus for GNOME/Wayland
            result = subprocess.run(
                [
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell",
                    "--object-path",
                    "/org/gnome/Shell",
                    "--method",
                    "org.gnome.Shell.Eval",
                    "global.display.focus_window ? "
                    "global.display.focus_window.get_wm_class() + '|' + "
                    "global.display.focus_window.get_title() : ''",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # Parse the gdbus output
                if "|" in output:
                    parts = output.split("|", 1)
                    return (parts[0].strip("' (),"), parts[1].strip("' (),"))
        except FileNotFoundError:
            pass

        return ("Unknown", "")

    elif system == "Windows":
        try:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Form]::ActiveForm"
            )
            # Use a simpler approach with ctypes via python
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            window_title = buf.value

            # Get process name
            import ctypes.wintypes

            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    f"(Get-Process -Id {pid.value}).ProcessName",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            app_name = result.stdout.strip() if result.returncode == 0 else "Unknown"
            return (app_name, window_title)
        except Exception:
            return ("Unknown", "")

    return ("Unknown", "")


class ApplicationMonitor(BaseMonitor):
    """Periodically polls the active application and window title."""

    def __init__(self, config: dict, db_session_factory, keyboard_monitor=None):
        super().__init__(config, db_session_factory)
        self._keyboard_monitor = keyboard_monitor
        self._poll_interval = config.get("monitoring", {}).get(
            "applications", {}
        ).get("poll_interval_seconds", 5)

    def _run(self):
        last_app = ""
        last_window = ""
        last_switch_time = datetime.utcnow()

        while self._running:
            app_name, window_title = get_active_window_info()

            # Update keyboard monitor with current window
            if self._keyboard_monitor:
                self._keyboard_monitor.set_active_window(app_name, window_title)

            # Detect app/window switch
            if app_name != last_app or window_title != last_window:
                if last_app:
                    duration = (datetime.utcnow() - last_switch_time).total_seconds()
                    self._record_usage(last_app, last_window, duration)

                last_app = app_name
                last_window = window_title
                last_switch_time = datetime.utcnow()

            time.sleep(self._poll_interval)

        # Record the last session on stop
        if last_app:
            duration = (datetime.utcnow() - last_switch_time).total_seconds()
            self._record_usage(last_app, last_window, duration)

    def _record_usage(self, app: str, window: str, duration: float):
        if duration < 1:
            return

        session = self._get_session()
        try:
            record = ApplicationUsage(
                application_name=app[:200],
                window_title=window[:500],
                duration_seconds=duration,
                category=_categorize_app(app),
            )
            session.add(record)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to record app usage")
        finally:
            session.close()
