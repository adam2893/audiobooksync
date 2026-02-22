"""Hardcovers API client using GraphQL."""

import httpx
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class HardcoversClient:
    """Client for Hardcovers GraphQL API."""

    API_URL = "https://api.hardcover.app/graphql"

    def __init__(self, api_key: str):
        """
        Initialize Hardcovers client.
        
        Args:
            api_key: API key from hardcover.app/account/api
        """
        self.api_key = api_key
        self.session = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create async HTTP session."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return self.session

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None

    async def _graphql_query(self, query: str, variables: Optional[dict] = None) -> dict[str, Any]:
        """Execute a GraphQL query."""
        if not self.api_key:
            logger.error("Hardcovers API key not configured")
            return {}

        try:
            session = await self._get_session()
            response = await session.post(
                self.API_URL,
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                logger.error(f"GraphQL error: {error_msg}")
                return {}
            
            return data.get("data", {})
        except Exception as e:
            logger.error(f"Failed to execute GraphQL query: {e}")
            return {}

    async def search_books(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for books on Hardcovers."""
        if not query.strip():
            return []

        gql_query = """
            query SearchBooks($query: String!, $limit: Int!) {
                search(query: $query, limit: $limit) {
                    books {
                        id
                        title
                        authors {
                            name
                        }
                        isbn13
                    }
                }
            }
        """
        
        try:
            data = await self._graphql_query(gql_query, {"query": query, "limit": limit})
            search_results = data.get("search", {}).get("books", [])
            return search_results
        except Exception as e:
            logger.error(f"Failed to search books: {e}")
            return []

    async def get_book_by_isbn(self, isbn: str) -> Optional[dict[str, Any]]:
        """Get book details by ISBN."""
        gql_query = """
            query GetBookByIsbn($isbn: String!) {
                bookByIsbn(isbn: $isbn) {
                    id
                    title
                    authors {
                        name
                    }
                    isbn13
                    imageUrl
                }
            }
        """
        
        try:
            data = await self._graphql_query(gql_query, {"isbn": isbn})
            return data.get("bookByIsbn")
        except Exception as e:
            logger.error(f"Failed to get book by ISBN {isbn}: {e}")
            return None

    async def update_reading_progress(
        self, book_id: str, progress_percent: float
    ) -> bool:
        """Update reading progress for a book."""
        gql_query = """
            mutation UpdateProgress($bookId: ID!, $progressPercent: Float!) {
                updateReadingProgress(bookId: $bookId, progressPercent: $progressPercent) {
                    success
                }
            }
        """
        
        try:
            data = await self._graphql_query(
                gql_query, {"bookId": book_id, "progressPercent": progress_percent}
            )
            return data.get("updateReadingProgress", {}).get("success", False)
        except Exception as e:
            logger.error(f"Failed to update progress for book {book_id}: {e}")
            return False

    async def validate_connection(self) -> bool:
        """Validate connection to Hardcovers API."""
        if not self.api_key:
            return False

        gql_query = "query { me { id } }"
        
        try:
            data = await self._graphql_query(gql_query)
            return "me" in data and data["me"] is not None
        except Exception:
            return False
