"""Sync worker for synchronizing progress across platforms."""

import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from src.models import AudioBook, BookMapping, SyncJob
from src.apis.audiobookshelf import AudiobookShelfClient
from src.apis.hardcovers import HardcoversClient
from src.apis.storygraph import StoryGraphClient

logger = logging.getLogger(__name__)


class SyncWorker:
    """Worker for syncing audiobook progress to platforms."""

    def __init__(
        self,
        abs_client: AudiobookShelfClient,
        hardcovers_client: HardcoversClient,
        storygraph_client: StoryGraphClient,
    ):
        """
        Initialize sync worker.
        
        Args:
            abs_client: AudiobookShelf API client
            hardcovers_client: Hardcovers API client
            storygraph_client: StoryGraph API client
        """
        self.abs = abs_client
        self.hardcovers = hardcovers_client
        self.storygraph = storygraph_client

    async def sync_book_progress(
        self,
        book: AudioBook,
        db: Session,
    ) -> bool:
        """
        Sync a book's progress to all mapped platforms.
        
        Args:
            book: AudioBook to sync
            db: Database session
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get mappings for this book
            mappings = db.query(BookMapping).filter(
                BookMapping.audiobook_id == book.id
            ).all()

            if not mappings:
                logger.debug(f"No platform mappings found for {book.title}")
                return False

            success_count = 0

            for mapping in mappings:
                if mapping.platform == "hardcovers":
                    result = await self._sync_to_hardcovers(book, mapping)
                elif mapping.platform == "storygraph":
                    result = await self._sync_to_storygraph(book, mapping)
                else:
                    logger.warning(f"Unknown platform: {mapping.platform}")
                    continue

                if result:
                    success_count += 1

            # Update last sync time
            book.last_synced_at = datetime.utcnow()
            db.commit()

            return success_count > 0

        except Exception as e:
            logger.error(f"Error syncing book {book.title}: {e}")
            return False

    async def _sync_to_hardcovers(
        self, book: AudioBook, mapping: BookMapping
    ) -> bool:
        """Sync progress to Hardcovers."""
        try:
            if book.total_duration == 0:
                logger.warning(f"No duration info for {book.title}, skipping Hardcovers sync")
                return False

            progress_percent = (book.current_progress / book.total_duration * 100) if book.total_duration > 0 else 0
            progress_percent = min(100, max(0, progress_percent))  # Clamp 0-100

            result = await self.hardcovers.update_reading_progress(
                book_id=mapping.platform_book_id,
                progress_percent=progress_percent,
            )

            if result:
                logger.info(
                    f"Synced {book.title} to Hardcovers: {progress_percent:.1f}%"
                )
                return True
            else:
                logger.warning(f"Failed to sync {book.title} to Hardcovers")
                return False

        except Exception as e:
            logger.error(f"Error syncing to Hardcovers for {book.title}: {e}")
            return False

    async def _sync_to_storygraph(
        self, book: AudioBook, mapping: BookMapping
    ) -> bool:
        """Sync progress to StoryGraph."""
        try:
            if book.total_duration == 0:
                logger.warning(f"No duration info for {book.title}, skipping StoryGraph sync")
                return False

            progress_percent = (book.current_progress / book.total_duration * 100) if book.total_duration > 0 else 0
            progress_percent = min(100, max(0, progress_percent))  # Clamp 0-100

            result = await self.storygraph.update_reading_progress(
                book_id=mapping.platform_book_id,
                progress=progress_percent,
                is_finished=book.is_finished,
            )

            if result:
                logger.info(
                    f"Synced {book.title} to StoryGraph: {progress_percent:.1f}%"
                )
                return True
            else:
                logger.warning(f"Failed to sync {book.title} to StoryGraph")
                return False

        except Exception as e:
            logger.error(f"Error syncing to StoryGraph for {book.title}: {e}")
            return False

    async def create_sync_job(
        self,
        db: Session,
        job_type: str,
        total_items: int,
    ) -> SyncJob:
        """Create a new sync job record."""
        job = SyncJob(
            job_type=job_type,
            status="running",
            total_items=total_items,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    async def update_sync_job(
        self,
        db: Session,
        job: SyncJob,
        processed_items: int,
        status: str = "running",
        error_message: Optional[str] = None,
    ):
        """Update sync job progress."""
        job.processed_items = processed_items
        job.status = status
        job.error_message = error_message
        if status in ["completed", "failed"]:
            job.completed_at = datetime.utcnow()
        db.commit()
