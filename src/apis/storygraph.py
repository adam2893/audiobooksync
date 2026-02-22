"""StoryGraph API client using web scraping."""

import httpx
import logging
from typing import Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class StoryGraphClient:
    """Client for StoryGraph using web scraping via HTTP."""

    BASE_URL = "https://www.storygraph.com"

    def __init__(self, session_cookie: str):
        """
        Initialize StoryGraph client.
        
        Args:
            session_cookie: _storygraph_session cookie extracted from browser
        """
        self.session_cookie = session_cookie
        self.session = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self.session is None:
            cookies = {"_storygraph_session": self.session_cookie}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            self.session = httpx.AsyncClient(
                timeout=30.0,
                cookies=cookies,
                headers=headers,
            )
        return self.session

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        """Search for books on StoryGraph."""
        if not query.strip() or not self.session_cookie:
            return []
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"{self.BASE_URL}/search",
                params={"q": query},
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            # Parse search results from HTML
            book_items = soup.find_all("div", class_="book-item")
            for item in book_items[:10]:  # Limit to 10 results
                try:
                    title_elem = item.find("h2")
                    author_elem = item.find("p", class_="author")
                    link = item.find("a", href=True)
                    
                    if title_elem and link:
                        results.append({
                            "id": link.get("href", "").split("/")[-1],
                            "title": title_elem.get_text(strip=True),
                            "author": author_elem.get_text(strip=True) if author_elem else "",
                            "url": link.get("href"),
                        })
                except Exception as e:
                    logger.debug(f"Error parsing book item: {e}")
                    continue
            
            return results
        except Exception as e:
            logger.error(f"Failed to search books: {e}")
            return []

    async def get_book(self, book_id: str) -> Optional[dict[str, Any]]:
        """Get book details by ID."""
        if not self.session_cookie:
            return None
        
        try:
            session = await self._get_session()
            response = await session.get(f"{self.BASE_URL}/books/{book_id}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title_elem = soup.find("h1", class_="book-title")
            author_elem = soup.find("a", class_="author-name")
            
            if title_elem:
                return {
                    "id": book_id,
                    "title": title_elem.get_text(strip=True),
                    "author": author_elem.get_text(strip=True) if author_elem else "",
                    "url": f"{self.BASE_URL}/books/{book_id}",
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
        
        Note: StoryGraph does not have a public API for this. This would require
        HTML form scraping and authentication. Currently returns False to indicate
        updates are not supported via the public interface.
        
        Args:
            book_id: StoryGraph book ID
            progress: Progress as percentage (0-100) or pages
            is_finished: Whether the book is finished
        
        Returns:
            False - StoryGraph read-only (no public API for progress updates)
        """
        if not self.session_cookie:
            return False
        
        logger.warning(
            f"StoryGraph progress update requested for book {book_id}, "
            "but StoryGraph does not have a public API for this. "
            "Updates must be done manually on the StoryGraph website."
        )
        return False

    async def validate_connection(self) -> bool:
        """Validate connection to StoryGraph."""
        if not self.session_cookie:
            return False
        
        try:
            session = await self._get_session()
            response = await session.get(self.BASE_URL)
            # If we get a successful response and the session is valid, we're good
            return response.status_code == 200
        except Exception:
            return False
