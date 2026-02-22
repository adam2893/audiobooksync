"""StoryGraph API client using storygraph-wrapper."""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class StoryGraphClient:
    """Client for StoryGraph API using unofficial wrapper."""

    def __init__(self, session_cookie: str):
        """
        Initialize StoryGraph client.
        
        Args:
            session_cookie: _storygraph_session cookie extracted from browser
        """
        self.session_cookie = session_cookie
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the StoryGraph wrapper client."""
        try:
            from storygraph_wrapper import StoryGraphClient as SGClient
            
            self.client = SGClient(session_cookie=self.session_cookie)
        except ImportError:
            logger.error("storygraph-wrapper not installed")
            raise

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        """Search for books on StoryGraph."""
        try:
            results = self.client.search(query)
            if results:
                return [
                    {
                        "id": book.get("id"),
                        "title": book.get("title"),
                        "author": book.get("author"),
                        "url": book.get("url"),
                    }
                    for book in results
                ]
            return []
        except Exception as e:
            logger.error(f"Failed to search books: {e}")
            return []

    async def get_book(self, book_id: str) -> Optional[dict[str, Any]]:
        """Get book details by ID."""
        try:
            book = self.client.get_book(book_id)
            if book:
                return {
                    "id": book.get("id"),
                    "title": book.get("title"),
                    "author": book.get("author"),
                    "url": book.get("url"),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get book {book_id}: {e}")
            return None

    async def update_reading_progress(
        self, book_id: str, progress: float, is_finished: bool = False
    ) -> bool:
        """
        Update reading progress for a book.
        
        Args:
            book_id: StoryGraph book ID
            progress: Progress as percentage (0-100) or pages
            is_finished: Whether the book is finished
        
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.client.update_progress(
                book_id=book_id,
                progress=progress,
                is_finished=is_finished,
            )
            return result
        except Exception as e:
            logger.error(f"Failed to update progress for book {book_id}: {e}")
            return False

    async def validate_connection(self) -> bool:
        """Validate connection to StoryGraph."""
        try:
            # Try to get user's profile to validate session
            profile = self.client.get_profile()
            return profile is not None
        except Exception as e:
            logger.error(f"Failed to validate StoryGraph connection: {e}")
            return False
