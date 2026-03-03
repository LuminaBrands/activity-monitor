"""Periodic screenshot capture."""

import logging
import os
import time
from datetime import datetime
from pathlib import Path

from activity_monitor.monitors.application import get_active_window_info
from activity_monitor.monitors.base import BaseMonitor
from activity_monitor.storage.models import Screenshot

logger = logging.getLogger(__name__)


class ScreenshotMonitor(BaseMonitor):
    """Captures screenshots at regular intervals."""

    def __init__(self, config: dict, db_session_factory):
        super().__init__(config, db_session_factory)
        ss_config = config.get("monitoring", {}).get("screenshots", {})
        self._interval = ss_config.get("interval_seconds", 300)
        self._storage_path = ss_config.get("storage_path", "screenshots")
        self._quality = ss_config.get("quality", 50)
        self._max_storage_bytes = ss_config.get("max_storage_gb", 5) * 1024**3

    def _run(self):
        # Ensure storage directory exists
        Path(self._storage_path).mkdir(parents=True, exist_ok=True)

        while self._running:
            self._capture()
            # Sleep in small increments so we can stop promptly
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)

    def _capture(self):
        try:
            import mss
            from PIL import Image
        except ImportError:
            logger.error(
                "mss or Pillow not installed — screenshot monitoring disabled. "
                "Install with: pip install mss Pillow"
            )
            self._running = False
            return

        now = datetime.utcnow()
        date_dir = os.path.join(self._storage_path, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        filename = now.strftime("%H-%M-%S") + ".jpg"
        filepath = os.path.join(date_dir, filename)

        try:
            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

                # Resize to reduce storage (keep aspect ratio, max 1920 wide)
                max_width = 1920
                if img.width > max_width:
                    ratio = max_width / img.width
                    img = img.resize(
                        (max_width, int(img.height * ratio)), Image.LANCZOS
                    )

                img.save(filepath, "JPEG", quality=self._quality)

            file_size = os.path.getsize(filepath)
            app_name, window_title = get_active_window_info()

            session = self._get_session()
            try:
                record = Screenshot(
                    file_path=filepath,
                    active_application=app_name[:200],
                    active_window_title=window_title[:500],
                    file_size_bytes=file_size,
                )
                session.add(record)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Failed to save screenshot metadata")
            finally:
                session.close()

            logger.debug("Screenshot saved: %s (%d bytes)", filepath, file_size)

            self._enforce_storage_limit()

        except Exception:
            logger.exception("Failed to capture screenshot")

    def _enforce_storage_limit(self):
        """Delete oldest screenshots if total storage exceeds the limit."""
        storage_path = Path(self._storage_path)
        if not storage_path.exists():
            return

        all_files = sorted(storage_path.rglob("*.jpg"), key=lambda f: f.stat().st_mtime)
        total_size = sum(f.stat().st_size for f in all_files)

        while total_size > self._max_storage_bytes and all_files:
            oldest = all_files.pop(0)
            total_size -= oldest.stat().st_size
            oldest.unlink()
            logger.info("Deleted old screenshot: %s", oldest)
