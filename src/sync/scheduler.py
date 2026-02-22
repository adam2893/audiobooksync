"""Scheduler for periodic sync tasks."""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Settings
from src.models import Base, AudioBook

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Manages scheduled sync tasks."""

    def __init__(self, settings: Settings):
        """
        Initialize scheduler.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.scheduler = None
        self.db_engine = None
        self.SessionLocal = None

    async def initialize(self):
        """Initialize scheduler and database."""
        try:
            # Set up database
            self.db_engine = create_engine(
                self.settings.database_url,
                echo=False,
            )
            
            # Create tables
            Base.metadata.create_all(self.db_engine)
            self.SessionLocal = sessionmaker(bind=self.db_engine)

            # Set up scheduler with SQLite backend
            jobstores = {
                "default": SQLAlchemyJobStore(engine=self.db_engine)
            }

            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                timezone="UTC",
            )

            logger.info("Scheduler initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            raise

    async def add_periodic_sync_job(
        self,
        sync_function,
        interval_minutes: int,
        job_id: str = "periodic_sync",
    ):
        """
        Add periodic sync job to scheduler.
        
        Args:
            sync_function: Async function to execute
            interval_minutes: Interval in minutes
            job_id: Unique job identifier
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        try:
            # Remove existing job if present
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass

            # Add new job
            self.scheduler.add_job(
                sync_function,
                "interval",
                minutes=interval_minutes,
                id=job_id,
                name=f"Periodic sync every {interval_minutes} minutes",
                replace_existing=True,
            )

            logger.info(
                f"Added periodic sync job: every {interval_minutes} minutes"
            )

        except Exception as e:
            logger.error(f"Failed to add periodic sync job: {e}")
            raise

    async def start(self):
        """Start the scheduler."""
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        try:
            self.scheduler.start()
            logger.info("Scheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    async def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")

    def get_session(self):
        """Get a database session."""
        if not self.SessionLocal:
            raise RuntimeError("Scheduler not initialized")
        return self.SessionLocal()

    async def get_sync_stats(self) -> dict:
        """Get current sync statistics."""
        try:
            db = self.get_session()
            total_books = db.query(AudioBook).count()
            synced_books = db.query(AudioBook).filter(
                AudioBook.last_synced_at.isnot(None)
            ).count()
            db.close()

            return {
                "total_books": total_books,
                "synced_books": synced_books,
                "pending_books": total_books - synced_books,
                "scheduler_running": self.scheduler.running if self.scheduler else False,
            }
        except Exception as e:
            logger.error(f"Error getting sync stats: {e}")
            return {
                "total_books": 0,
                "synced_books": 0,
                "pending_books": 0,
                "scheduler_running": False,
            }
