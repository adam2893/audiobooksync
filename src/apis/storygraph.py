"""StoryGraph API client with dual authentication support."""

import httpx
import logging
from typing import Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class StoryGraphClient:
    """Client for StoryGraph supporting both cookie and username/password authentication."""

    BASE_URL = "https://www.storygraph.com"

    def __init__(
        self,
        session_cookie: str = "",
        username: str = "",
        password: str = "",
    ):
        """
        Initialize StoryGraph client with dual authentication support.
        
        Args:
            session_cookie: _storygraph_session cookie (read-only mode)
            username: StoryGraph username (read+write mode)
            password: StoryGraph password (read+write mode)
        
        Priority: username/password > session_cookie
        """
        self.session_cookie = session_cookie
        self.username = username
        self.password = password
        self.session = None
        self.auth_method = None
        self._determine_auth_method()

    def _determine_auth_method(self):
        """Determine which authentication method to use."""
        has_credentials = self.username and self.username.strip() and self.password and self.password.strip()
        has_cookie = self.session_cookie and self.session_cookie.strip()
        
        if has_credentials:
            self.auth_method = "username_password"
        elif has_cookie:
            self.auth_method = "cookie"
        else:
            self.auth_method = "none"
        
        logger.info(f"StoryGraph auth method: {self.auth_method}")

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self.session is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            if self.auth_method == "username_password":
                # Create session for username/password auth
                self.session = httpx.AsyncClient(
                    timeout=30.0,
                    headers=headers,
                )
                # Login first
                await self._login()
            elif self.auth_method == "cookie":
                # Create session with cookie authentication
                cookies = {"_storygraph_session": self.session_cookie}
                self.session = httpx.AsyncClient(
                    timeout=30.0,
                    cookies=cookies,
                    headers=headers,
                )
            else:
                # No auth - just create basic session
                self.session = httpx.AsyncClient(
                    timeout=30.0,
                    headers=headers,
                )
        
        return self.session

    async def _login(self):
        """Login to StoryGraph using username/password."""
        if not self.username or not self.password:
            logger.warning("Cannot login: username or password not provided")
            return
        
        try:
            # Try to import and use storygraph-api if available
            try:
                from storygraph_api import StorygraphClient as SGApi
                
                logger.info("Using storygraph-api for authentication")
                api_client = SGApi()
                await api_client.login(self.username, self.password)
                
                # If login successful, copy cookies to our session
                if self.session and hasattr(api_client, 'cookies'):
                    self.session.cookies.update(api_client.cookies)
                
            except ImportError:
                logger.warning("storygraph-api not installed, falling back to manual login")
                # Fallback: manual login attempt
                login_response = await self.session.post(
                    f"{self.BASE_URL}/api/login",
                    json={"username": self.username, "password": self.password},
                )
                login_response.raise_for_status()
                
        except Exception as e:
            logger.error(f"Failed to login to StoryGraph: {e}")
            self.auth_method = "none"

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def search_books(self, query: str) -> list[dict[str, Any]]:
        """Search for books on StoryGraph."""
        if not query.strip() or self.auth_method == "none":
            return []
        
        try:
            # Try to use storygraph-api if using password auth
            if self.auth_method == "username_password":
                try:
                    from storygraph_api import StorygraphClient as SGApi
                    
                    api_client = SGApi()
                    # Search would require login - for now return empty
                    logger.debug("storygraph-api search not fully implemented")
                    return []
                except ImportError:
                    logger.warning("storygraph-api not installed, falling back to HTML scraping")
                    # Continue to HTML scraping below
            
            # HTML scraping for cookie auth or fallback
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
        if self.auth_method == "none":
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
        
        Supports two methods:
        1. Username/password auth: Uses storygraph-api for actual API calls (if available)
        2. Cookie auth: Read-only (no API support)
        
        Args:
            book_id: StoryGraph book ID
            progress: Progress as percentage (0-100) or pages
            is_finished: Whether the book is finished
        
        Returns:
            True if successful, False otherwise
        """
        if self.auth_method == "none":
            return False
        
        if self.auth_method == "cookie":
            # Cookie auth is read-only
            logger.warning(
                f"StoryGraph progress update requested for book {book_id}, "
                "but cookie authentication is read-only. "
                "Use username/password authentication for write support, "
                "or update manually on the StoryGraph website."
            )
            return False
        
        if self.auth_method == "username_password":
            # Try to use storygraph-api if available
            try:
                from storygraph_api import StorygraphClient as SGApi
                
                api_client = SGApi()
                # Note: This would need the login flow to be implemented properly
                # For now, return False as placeholder
                logger.warning(
                    "storygraph-api support for progress updates is not yet fully implemented. "
                    "Please implement the actual update method using storygraph-api."
                )
                return False
                
            except ImportError:
                logger.warning("storygraph-api not installed - cannot update progress")
                return False
            except Exception as e:
                logger.error(f"Error updating StoryGraph progress: {e}")
                return False
        
        return False

    async def validate_connection(self) -> bool:
        """Validate connection to StoryGraph."""
        if self.auth_method == "none":
            return False
        
        try:
            session = await self._get_session()
            if session is None:
                return False
            response = await session.get(self.BASE_URL)
            # If we get a successful response, connection is valid
            return response.status_code == 200
        except Exception as e:
            logger.error(f"StoryGraph connection validation failed: {e}")
            return False

