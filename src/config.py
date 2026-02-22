"""Configuration management for AudioBook Sync."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # AudiobookShelf (required but can be empty initially)
    audiobookshelf_url: str = ""
    audiobookshelf_api_key: str = ""

    # Hardcovers (optional)
    hardcovers_api_key: str = ""

    # StoryGraph (optional)
    storygraph_session_cookie: str = ""

    # Sync Configuration
    sync_interval_minutes: int = 10
    auto_match_on_first_run: bool = True
    sync_one_way: bool = True

    # Application
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/sync.db"
    web_ui_port: int = 8000
    web_ui_host: str = "0.0.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


def validate_settings(settings: Settings) -> dict[str, str]:
    """
    Validate all settings and return errors if any.
    
    Returns:
        Dictionary with field names as keys and error messages as values.
    """
    errors = {}

    # Validate AudiobookShelf (required)
    if not settings.audiobookshelf_url or not settings.audiobookshelf_url.strip():
        errors["audiobookshelf_url"] = (
            "AudiobookShelf URL is required. "
            "Set AUDIOBOOKSHELF_URL environment variable (e.g., http://localhost:13378)"
        )
    if not settings.audiobookshelf_api_key or not settings.audiobookshelf_api_key.strip():
        errors["audiobookshelf_api_key"] = (
            "AudiobookShelf API key is required. "
            "Get it from AudiobookShelf settings → API Tokens"
        )

    # Validate Hardcovers (optional but warn if not set)
    if not settings.hardcovers_api_key or not settings.hardcovers_api_key.strip():
        errors["hardcovers_api_key"] = (
            "Hardcovers API key is not set (optional). "
            "Get it from hardcover.app/account/api to enable Hardcovers sync"
        )

    # Validate StoryGraph (optional but warn if not set)
    if not settings.storygraph_session_cookie or not settings.storygraph_session_cookie.strip():
        errors["storygraph_session_cookie"] = (
            "StoryGraph session cookie is not set (optional). "
            "See documentation for how to extract your session cookie to enable StoryGraph sync"
        )

    return errors
