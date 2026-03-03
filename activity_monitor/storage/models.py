"""SQLAlchemy models for activity data storage."""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class KeyboardActivity(Base):
    """Tracks typing activity in time windows (not raw keystrokes for privacy)."""

    __tablename__ = "keyboard_activity"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    window_title = Column(String(500))
    application = Column(String(200))
    key_count = Column(Integer, default=0)
    # Rolling minute-level activity bucket
    minute_bucket = Column(String(16), index=True)  # "YYYY-MM-DD HH:MM"


class ApplicationUsage(Base):
    """Tracks which applications and windows were active."""

    __tablename__ = "application_usage"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    application_name = Column(String(200), index=True)
    window_title = Column(String(500))
    duration_seconds = Column(Float, default=0)
    # Category: coding, browsing, communication, design, etc.
    category = Column(String(100))


class Screenshot(Base):
    """Metadata for captured screenshots."""

    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    file_path = Column(String(500))
    active_application = Column(String(200))
    active_window_title = Column(String(500))
    file_size_bytes = Column(Integer)


class CommunicationEvent(Base):
    """Tracks when communication apps were actively used."""

    __tablename__ = "communication_events"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    application = Column(String(200))
    window_title = Column(String(500))
    duration_seconds = Column(Float, default=0)
    # Inferred context from window title (channel name, email subject, etc.)
    context = Column(String(500))


class DailySummary(Base):
    """Stores generated daily summaries."""

    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True)
    date = Column(String(10), unique=True, index=True)  # "YYYY-MM-DD"
    generated_at = Column(DateTime, default=datetime.utcnow)
    summary_text = Column(Text)
    conversations_text = Column(Text)
    plan_text = Column(Text)
    # Raw stats
    total_active_minutes = Column(Integer)
    total_keystrokes = Column(Integer)
    top_applications = Column(Text)  # JSON


class Database:
    """Database connection and session management."""

    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self._session_factory()
