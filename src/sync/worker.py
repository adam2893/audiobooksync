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
    async def run_periodic_sync(self, db: Session) -> dict:
        """
        Periodic sync function to run on a schedule.
        
        Fetches new books from AudiobookShelf and syncs progress to all mapped platforms.
        
        Args:
            db: Database session
            
        Returns:
            Dict with sync results: {synced_count, failed_count, errors}
        """
        logger.info("Starting periodic sync...")
        
        # Create sync job for auditing
        job = await self.create_sync_job(db, "sync_progress", 0)
        
        synced_count = 0
        failed_count = 0
        errors = []
        
        try:
            # Get all libraries from AudiobookShelf
            libraries = await self.abs.get_user_libraries()
            if not libraries:
                logger.warning("No libraries found in AudiobookShelf")
                await self.update_sync_job(db, job, 0, "completed")
                return {"synced_count": 0, "failed_count": 0, "errors": []}
            
            total_books = 0
            
            # Iterate through each library and sync books
            for library in libraries:
                library_id = library.get("id")
                try:
                    items = await self.abs.get_library_items(library_id)
                    total_books += len(items)
                    
                    for item in items:
                        try:
                            book_id = item.get("id")
                            
                            # Get progress from AudiobookShelf
                            progress_data = await self.abs.get_progress(book_id)
                            if not progress_data:
                                continue
                            
                            # Get or create book in database
                            book = db.query(AudioBook).filter(
                                AudioBook.audiobookshelf_id == book_id
                            ).first()
                            
                            if not book:
                                book = AudioBook(
                                    audiobookshelf_id=book_id,
                                    title=item.get("title", "Unknown"),
                                    author=item.get("author", "Unknown"),
                                    isbn=item.get("isbn", ""),
                                )
                                db.add(book)
                                db.commit()
                                db.refresh(book)
                            
                            # Update book progress
                            book.current_progress = progress_data.get("progress", 0)
                            book.is_finished = progress_data.get("isFinished", False)
                            book.total_duration = progress_data.get("duration", 0)
                            book.last_synced_at = datetime.utcnow()
                            db.commit()
                            
                            # Sync to all mapped platforms
                            if await self.sync_book_progress(book, db):
                                synced_count += 1
                            else:
                                failed_count += 1
                                
                        except Exception as e:
                            failed_count += 1
                            error_msg = f"Error syncing book {book_id}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                        
                        # Update job progress
                        await self.update_sync_job(db, job, synced_count + failed_count)
                        
                except Exception as e:
                    error_msg = f"Error syncing library {library_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Mark job as completed
            await self.update_sync_job(
                db, job, synced_count + failed_count, "completed"
            )
            logger.info(
                f"Periodic sync completed: {synced_count} synced, {failed_count} failed"
            )
            
            return {
                "synced_count": synced_count,
                "failed_count": failed_count,
                "total_books": total_books,
                "errors": errors,
            }
            
        except Exception as e:
            error_msg = f"Fatal error during periodic sync: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self.update_sync_job(db, job, 0, "failed", error_msg)
            return {
                "synced_count": 0,
                "failed_count": 0,
                "errors": [error_msg],
            }