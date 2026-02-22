"""Book matching engine for cross-platform synchronization."""

import logging
from typing import Optional, Any
from fuzzywuzzy import fuzz
from datetime import datetime
from sqlalchemy.orm import Session

from src.models import AudioBook, BookMapping
from src.apis.hardcovers import HardcoversClient
from src.apis.storygraph import StoryGraphClient

logger = logging.getLogger(__name__)


class BookMatcher:
    """Matches books across platforms using ISBN and fuzzy matching."""

    MIN_FUZZY_SCORE = 80  # Minimum score for fuzzy matching to be considered valid

    def __init__(
        self,
        hardcovers_client: HardcoversClient,
        storygraph_client: StoryGraphClient,
    ):
        """
        Initialize book matcher.
        
        Args:
            hardcovers_client: Hardcovers API client
            storygraph_client: StoryGraph API client
        """
        self.hardcovers = hardcovers_client
        self.storygraph = storygraph_client

    async def match_book_on_platform(
        self,
        book: AudioBook,
        platform: str,
        db: Session,
    ) -> Optional[dict[str, Any]]:
        """
        Match a book on a specific platform.
        
        Args:
            book: AudioBook to match
            platform: Target platform ("hardcovers" or "storygraph")
            db: Database session
        
        Returns:
            Dictionary with matched book info or None if no match found
        """
        try:
            # Check if already mapped
            existing_mapping = db.query(BookMapping).filter(
                BookMapping.audiobook_id == book.id,
                BookMapping.platform == platform,
            ).first()
            
            if existing_mapping:
                logger.info(f"Book {book.title} already mapped on {platform}")
                return {
                    "platform_id": existing_mapping.platform_book_id,
                    "confidence": existing_mapping.match_confidence,
                    "is_manual": existing_mapping.is_manual_override,
                }

            # Try ISBN match first
            if book.isbn:
                match = await self._match_by_isbn(book, platform)
                if match:
                    return match

            # Fallback to fuzzy title/author match
            match = await self._match_by_fuzzy(book, platform)
            return match

        except Exception as e:
            logger.error(f"Error matching book {book.title} on {platform}: {e}")
            return None

    async def _match_by_isbn(
        self, book: AudioBook, platform: str
    ) -> Optional[dict[str, Any]]:
        """Match book by ISBN."""
        try:
            if platform == "hardcovers":
                result = await self.hardcovers.get_book_by_isbn(book.isbn)
                if result:
                    logger.info(
                        f"ISBN match found for {book.title} on Hardcovers: {result['id']}"
                    )
                    return {
                        "platform_id": result["id"],
                        "confidence": 1.0,
                        "title": result.get("title"),
                        "authors": result.get("authors", []),
                    }
            elif platform == "storygraph":
                # StoryGraph wrapper doesn't have ISBN lookup, use fuzzy fallback
                pass

            return None
        except Exception as e:
            logger.debug(f"ISBN match failed for {book.isbn} on {platform}: {e}")
            return None

    async def _match_by_fuzzy(
        self, book: AudioBook, platform: str
    ) -> Optional[dict[str, Any]]:
        """Match book by fuzzy title/author comparison."""
        try:
            query = f"{book.title} {book.author}".strip()
            
            if platform == "hardcovers":
                results = await self.hardcovers.search_books(query, limit=5)
            elif platform == "storygraph":
                results = await self.storygraph.search_books(query)
            else:
                return None

            if not results:
                logger.info(f"No fuzzy matches found for {book.title} on {platform}")
                return None

            # Score each result
            best_match = None
            best_score = 0

            for result in results:
                result_title = result.get("title", "")
                result_authors = result.get("authors", [])
                
                if isinstance(result_authors, list):
                    result_author = " ".join(result_authors) if result_authors else ""
                else:
                    result_author = str(result_authors) if result_authors else ""

                result_text = f"{result_title} {result_author}".strip()

                # Calculate similarity score
                score = fuzz.token_set_ratio(query.lower(), result_text.lower())

                logger.debug(f"Fuzzy match score for {book.title}: {score}")

                if score > best_score and score >= self.MIN_FUZZY_SCORE:
                    best_score = score
                    best_match = {
                        "platform_id": result.get("id"),
                        "confidence": best_score / 100.0,  # Convert to 0-1 range
                        "title": result_title,
                        "authors": result_authors,
                    }

            if best_match:
                logger.info(
                    f"Fuzzy match found for {book.title} on {platform}: "
                    f"{best_match['title']} (confidence: {best_match['confidence']:.2f})"
                )

            return best_match

        except Exception as e:
            logger.error(f"Fuzzy matching failed for {book.title} on {platform}: {e}")
            return None

    async def save_match(
        self,
        db: Session,
        book_id: int,
        platform: str,
        platform_book_id: str,
        confidence: float,
        is_manual: bool = False,
    ) -> BookMapping:
        """Save book match to database."""
        mapping = BookMapping(
            audiobook_id=book_id,
            platform=platform,
            platform_book_id=platform_book_id,
            match_confidence=confidence,
            is_manual_override=is_manual,
        )
        db.add(mapping)
        db.commit()
        db.refresh(mapping)
        logger.info(f"Saved {platform} mapping for book {book_id}")
        return mapping

    async def match_all_books(
        self,
        db: Session,
        platforms: list[str] = None,
        progress_callback=None,
    ) -> dict[str, int]:
        """
        Match all unmapped books across specified platforms.
        
        Args:
            db: Database session
            platforms: List of platforms to match ("hardcovers", "storygraph")
            progress_callback: Async callback for progress updates
        
        Returns:
            Dictionary with match counts per platform
        """
        if platforms is None:
            platforms = ["hardcovers", "storygraph"]

        results = {platform: 0 for platform in platforms}

        # Get all books without mappings
        books = db.query(AudioBook).all()
        total_books = len(books)

        logger.info(f"Starting to match {total_books} books")

        for idx, book in enumerate(books):
            for platform in platforms:
                # Check if already mapped
                existing = db.query(BookMapping).filter(
                    BookMapping.audiobook_id == book.id,
                    BookMapping.platform == platform,
                ).first()

                if not existing:
                    match = await self.match_book_on_platform(book, platform, db)
                    if match:
                        await self.save_match(
                            db,
                            book.id,
                            platform,
                            match["platform_id"],
                            match.get("confidence", 1.0),
                        )
                        results[platform] += 1

            # Progress update
            if progress_callback:
                await progress_callback(
                    current=idx + 1,
                    total=total_books,
                    platform_results=results,
                )

        logger.info(f"Matching complete. Results: {results}")
        return results
