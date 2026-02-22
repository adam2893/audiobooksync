"""Configuration management for AudioBook Sync."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # AudiobookShelf
    audiobookshelf_url: str
    audiobookshelf_api_key: str

    # Hardcovers
    hardcovers_api_key: str

    # StoryGraph
    storygraph_session_cookie: str

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

    # Validate AudiobookShelf
    if not settings.audiobookshelf_url:
        errors["audiobookshelf_url"] = (
            "AudiobookShelf URL is required. "
            "Set AUDIOBOOKSHELF_URL environment variable (e.g., http://localhost:13378)"
        )
    if not settings.audiobookshelf_api_key:
        errors["audiobookshelf_api_key"] = (
            "AudiobookShelf API key is required. "
            "Get it from AudiobookShelf settings → API Tokens"
        )

    # Validate Hardcovers
    if not settings.hardcovers_api_key:
        errors["hardcovers_api_key"] = (
            "Hardcovers API key is required. "
            "Get it from hardcover.app/account/api"
        )

    # Validate StoryGraph
    if not settings.storygraph_session_cookie:
        errors["storygraph_session_cookie"] = (
            "StoryGraph session cookie is required. "
            "See documentation for how to extract your session cookie"
        )

    return errors
