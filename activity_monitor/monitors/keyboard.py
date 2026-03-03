"""Keyboard activity monitor — tracks typing volume, not raw keystrokes."""

import logging
import time
from datetime import datetime

from activity_monitor.monitors.base import BaseMonitor
from activity_monitor.storage.models import KeyboardActivity

logger = logging.getLogger(__name__)


class KeyboardMonitor(BaseMonitor):
    """Monitors keyboard activity by counting keystrokes per minute bucket.

    For privacy, raw key values are not recorded by default — only
    the count of keys pressed per minute, along with the active
    application and window title at the time.
    """

    def __init__(self, config: dict, db_session_factory):
        super().__init__(config, db_session_factory)
        self._current_count = 0
        self._last_flush = datetime.utcnow()
        self._current_app = ""
        self._current_window = ""

    def set_active_window(self, app: str, window: str):
        """Called by the application monitor to keep window info in sync."""
        self._current_app = app
        self._current_window = window

    def _run(self):
        try:
            from pynput import keyboard
        except ImportError:
            logger.error(
                "pynput not installed — keyboard monitoring disabled. "
                "Install with: pip install pynput"
            )
            return

        def on_press(key):
            self._current_count += 1

        listener = keyboard.Listener(on_press=on_press)
        listener.start()

        try:
            while self._running:
                time.sleep(10)
                self._flush_counts()
        finally:
            listener.stop()

    def _flush_counts(self):
        """Write accumulated keystrokes to the database."""
        if self._current_count == 0:
            return

        now = datetime.utcnow()
        minute_bucket = now.strftime("%Y-%m-%d %H:%M")
        count = self._current_count
        self._current_count = 0

        session = self._get_session()
        try:
            record = KeyboardActivity(
                timestamp=now,
                window_title=self._current_window[:500],
                application=self._current_app[:200],
                key_count=count,
                minute_bucket=minute_bucket,
            )
            session.add(record)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to flush keyboard activity")
        finally:
            session.close()
