"""Configuration management for AudioBook Sync."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # AudiobookShelf (required)
    audiobookshelf_url: str = Field(default="", env="AUDIOBOOKSHELF_URL")
    audiobookshelf_api_key: str = Field(default="", env="AUDIOBOOKSHELF_API_KEY")

    # Hardcovers (optional)
    hardcovers_api_key: str = Field(default="", env="HARDCOVERS_API_KEY")

    # StoryGraph (optional - choose one authentication method)
    # Option 1: Session cookie (read-only, more secure, no password stored)
    storygraph_session_cookie: str = Field(default="", env="STORYGRAPH_SESSION_COOKIE")
    # Option 2: Username/password (read+write, using storygraph-api)
    storygraph_username: str = Field(default="", env="STORYGRAPH_USERNAME")
    storygraph_password: str = Field(default="", env="STORYGRAPH_PASSWORD")

    # Sync Configuration
    sync_interval_minutes: int = Field(default=10, env="SYNC_INTERVAL_MINUTES")
    auto_match_on_first_run: bool = Field(default=True, env="AUTO_MATCH_ON_FIRST_RUN")
    sync_one_way: bool = Field(default=True, env="SYNC_ONE_WAY")

    # Application
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    database_url: str = Field(default="sqlite:///./data/sync.db", env="DATABASE_URL")
    web_ui_port: int = Field(default=8000, env="WEB_UI_PORT")
    web_ui_host: str = Field(default="0.0.0.0", env="WEB_UI_HOST")

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

    # Validate AudiobookShelf (optional at startup - can be configured via web UI)
    # Only validate if URL is provided
    if settings.audiobookshelf_url and settings.audiobookshelf_url.strip():
        if not settings.audiobookshelf_api_key or not settings.audiobookshelf_api_key.strip():
            errors["audiobookshelf_api_key"] = (
                "If AudiobookShelf URL is configured, API key is required. "
                "Get it from AudiobookShelf settings → API Tokens"
            )
    # If URL is not set, it's not an error - user can configure via web UI later

    # Validate Hardcovers (optional - truly optional, no errors)
    # These are optional integrations, don't add to errors dict

    # Validate StoryGraph (optional - two authentication options available)
    # Option 1: Session cookie (read-only, more secure)
    # Option 2: Username/password (read+write with storygraph-api)
    # User can provide either, both, or neither - all optional
    # No errors - just informational in validation response

    return errors


def can_run_sync(settings: Settings) -> bool:
    """Check if minimum required settings are present to run sync.
    
    Sync requires AudiobookShelf to be configured.
    """
    return bool(
        settings.audiobookshelf_url
        and settings.audiobookshelf_url.strip()
        and settings.audiobookshelf_api_key
        and settings.audiobookshelf_api_key.strip()
    )


def get_storygraph_auth_method(settings: Settings) -> str:
    """Determine which StoryGraph authentication method to use.
    
    Returns:
        "username_password" - if username and password are configured
        "cookie" - if session cookie is configured
        "none" - if neither is configured
    """
    has_credentials = (
        settings.storygraph_username
        and settings.storygraph_username.strip()
        and settings.storygraph_password
        and settings.storygraph_password.strip()
    )
    has_cookie = (
        settings.storygraph_session_cookie
        and settings.storygraph_session_cookie.strip()
    )
    
    if has_credentials:
        return "username_password"
    elif has_cookie:
        return "cookie"
    else:
        return "none"
