"""AudiobookShelf API client."""

import httpx
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class AudiobookShelfClient:
    """Client for AudiobookShelf API."""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize AudiobookShelf client.
        
        Args:
            base_url: Base URL of AudiobookShelf instance (e.g., http://localhost:13378)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
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

    async def get_user_libraries(self) -> list[dict[str, Any]]:
        """Get user's libraries."""
        if not self.base_url or not self.api_key:
            return []
        
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/api/me/libraries")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get libraries: {e}")
            return []

    async def get_library_items(self, library_id: str) -> list[dict[str, Any]]:
        """Get all library items in a library."""
        if not self.base_url or not self.api_key:
            return []
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"{self.base_url}/api/libraries/{library_id}/items",
                params={"limit": 10000},
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            logger.error(f"Failed to get library items: {e}")
            return []

    async def get_library_item(self, library_item_id: str) -> dict[str, Any]:
        """Get details of a specific library item."""
        if not self.base_url or not self.api_key:
            return {}
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"{self.base_url}/api/libraries/item/{library_item_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get library item {library_item_id}: {e}")
            return {}

    async def get_listening_sessions(self) -> list[dict[str, Any]]:
        """Get user's listening sessions."""
        if not self.base_url or not self.api_key:
            return []
        
        try:
            session = await self._get_session()
            response = await session.get(
                f"{self.base_url}/api/me/listening-sessions",
                params={"limit": 10000},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("sessions", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Failed to get listening sessions: {e}")
            return []

    async def get_progress(self, library_item_id: str) -> Optional[dict[str, Any]]:
        """Get progress for a specific library item."""
        if not self.base_url or not self.api_key:
            return None
        
        try:
            item = await self.get_library_item(library_item_id)
            if not item:
                return None
            media_progress = item.get("userMediaProgress", [])
            if media_progress:
                return media_progress[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get progress for {library_item_id}: {e}")
            return None

    async def validate_connection(self) -> bool:
        """Validate connection to AudiobookShelf."""
        if not self.base_url or not self.api_key:
            return False
        
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/api/me")
            return response.status_code == 200
        except Exception:
            return False
