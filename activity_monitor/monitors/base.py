"""Base class for all activity monitors."""

import logging
import threading
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class BaseMonitor(ABC):
    """Abstract base for activity monitors.

    Each monitor runs in its own thread and writes to the shared database.
    """

    def __init__(self, config: dict, db_session_factory):
        self.config = config
        self._db_session_factory = db_session_factory
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def _run(self):
        """Main monitoring loop. Must check self._running periodically."""

    def start(self):
        if self._running:
            logger.warning("%s is already running", self.name)
            return
        self._running = True
        self._thread = threading.Thread(target=self._safe_run, daemon=True)
        self._thread.start()
        logger.info("%s started", self.name)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("%s stopped", self.name)

    def _safe_run(self):
        try:
            self._run()
        except Exception:
            logger.exception("Error in %s", self.name)

    def _get_session(self):
        return self._db_session_factory()
