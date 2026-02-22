"""Database models for AudioBook Sync."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class AudioBook(Base):
    """AudioBook entity with cross-platform mappings."""

    __tablename__ = "audiobooks"

    id = Column(Integer, primary_key=True, index=True)
    audiobookshelf_id = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    author = Column(String, index=True)
    isbn = Column(String, index=True, nullable=True)

    # Progress tracking
    current_progress = Column(Float, default=0.0)
    total_duration = Column(Integer, default=0)
    is_finished = Column(Boolean, default=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Last sync timestamps
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    platform_mappings = relationship("BookMapping", back_populates="audiobook", cascade="all, delete-orphan")


class BookMapping(Base):
    """Mapping of books across different platforms."""

    __tablename__ = "book_mappings"

    id = Column(Integer, primary_key=True, index=True)
    audiobook_id = Column(Integer, ForeignKey("audiobooks.id"), index=True)
    platform = Column(String, index=True)  # "hardcovers", "storygraph"
    platform_book_id = Column(String)
    match_confidence = Column(Float, default=1.0)  # 0.0 to 1.0
    is_manual_override = Column(Boolean, default=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    audiobook = relationship("AudioBook", back_populates="platform_mappings")


class SyncJob(Base):
    """History of sync jobs for auditing and debugging."""

    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String)  # "auto_match", "sync_progress", "manual_match"
    status = Column(String)  # "pending", "running", "completed", "failed"
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)


class AppState(Base):
    """Application state tracking."""

    __tablename__ = "app_state"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
