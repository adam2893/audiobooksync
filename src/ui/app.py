"""FastAPI application and routes."""

import asyncio
import logging
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from src.config import get_settings, validate_settings, can_run_sync, get_storygraph_auth_method, Settings
from src.apis.audiobookshelf import AudiobookShelfClient
from src.apis.hardcovers import HardcoversClient
from src.apis.storygraph import StoryGraphClient
from src.sync.scheduler import SyncScheduler
from src.sync.matcher import BookMatcher
from src.sync.worker import SyncWorker
from src.logger import setup_logger

logger = setup_logger(__name__)

# Global state
app_state = {
    "settings": None,
    "scheduler": None,
    "abs_client": None,
    "hardcovers_client": None,
    "storygraph_client": None,
    "matcher": None,
    "worker": None,
    "config_errors": {},
    "setup_complete": False,
}


async def get_db():
    """Get database session."""
    if not app_state["scheduler"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not initialized",
        )
    db = app_state["scheduler"].get_session()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(title="AudioBook Sync", version="0.1.0")


# ============================================================================
# Startup and Shutdown
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        logger.info("Starting AudioBook Sync application...")

        # Load settings
        app_state["settings"] = get_settings()
        
        # Validate settings (only required fields must be valid)
        app_state["config_errors"] = validate_settings(app_state["settings"])

        # Check if we can actually run sync (requires AudiobookShelf)
        can_sync = can_run_sync(app_state["settings"])
        
        if app_state["config_errors"]:
            logger.warning(f"Configuration errors: {app_state['config_errors']}")
        elif can_sync:
            logger.info("AudiobookShelf is configured - sync can proceed")
            app_state["setup_complete"] = True
        else:
            logger.info("AudiobookShelf not configured - user must set up via web UI")

        # Initialize database and scheduler
        app_state["scheduler"] = SyncScheduler(app_state["settings"])
        await app_state["scheduler"].initialize()

        # Initialize API clients (even if config is incomplete, for testing)
        try:
            app_state["abs_client"] = AudiobookShelfClient(
                app_state["settings"].audiobookshelf_url,
                app_state["settings"].audiobookshelf_api_key,
            )
            app_state["hardcovers_client"] = HardcoversClient(
                app_state["settings"].hardcovers_api_key
            )
            app_state["storygraph_client"] = StoryGraphClient(
                session_cookie=app_state["settings"].storygraph_session_cookie,
                username=app_state["settings"].storygraph_username,
                password=app_state["settings"].storygraph_password,
            )

            # Initialize matcher and worker
            app_state["matcher"] = BookMatcher(
                app_state["hardcovers_client"],
                app_state["storygraph_client"],
            )
            app_state["worker"] = SyncWorker(
                app_state["abs_client"],
                app_state["hardcovers_client"],
                app_state["storygraph_client"],
            )

            logger.info("API clients initialized")

        except Exception as e:
            logger.error(f"Error initializing API clients: {e}")

        # Start scheduler if AudiobookShelf is configured
        if can_sync and app_state["worker"]:
            try:
                # Create a wrapper function for the periodic sync
                async def periodic_sync_job():
                    """Periodic sync job wrapper."""
                    db = app_state["scheduler"].get_session()
                    try:
                        await app_state["worker"].run_periodic_sync(db)
                    finally:
                        db.close()
                
                await app_state["scheduler"].add_periodic_sync_job(
                    sync_function=periodic_sync_job,
                    interval_minutes=app_state["settings"].sync_interval_minutes,
                    job_id="periodic_sync"
                )
                await app_state["scheduler"].start()
                logger.info("Scheduler started with periodic sync")
            except Exception as e:
                logger.error(f"Error starting scheduler: {e}")

        logger.info("AudioBook Sync startup complete")

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    try:
        logger.info("Shutting down AudioBook Sync...")

        if app_state["scheduler"]:
            await app_state["scheduler"].shutdown()

        # Close API clients
        if app_state["abs_client"]:
            await app_state["abs_client"].close()
        if app_state["hardcovers_client"]:
            await app_state["hardcovers_client"].close()
        if app_state["storygraph_client"]:
            await app_state["storygraph_client"].close()

        logger.info("Shutdown complete")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ============================================================================
# Health and Status Endpoints
# ============================================================================


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "scheduler_running": (
            app_state["scheduler"].scheduler.running
            if app_state["scheduler"]
            else False
        ),
    }


@app.get("/api/status")
async def get_status():
    """Get application status."""
    if not app_state["scheduler"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Application not initialized",
        )

    sync_stats = await app_state["scheduler"].get_sync_stats()

    return {
        "setup_complete": app_state["setup_complete"],
        "config_errors": app_state["config_errors"],
        "stats": sync_stats,
    }


# ============================================================================
# Configuration Endpoints
# ============================================================================


@app.get("/api/config/errors")
async def get_config_errors():
    """Get configuration validation errors with suggestions."""
    return app_state["config_errors"]


@app.post("/api/config/validate")
async def validate_config():
    """Validate current configuration."""
    settings = app_state["settings"]
    errors = validate_settings(settings)
    app_state["config_errors"] = errors

    if not errors:
        app_state["setup_complete"] = True

    return {"valid": len(errors) == 0, "errors": errors}


# ============================================================================
# Connection Validation Endpoints
# ============================================================================


@app.post("/api/validate/audiobookshelf")
async def validate_audiobookshelf():
    """Validate AudiobookShelf connection."""
    if not app_state["abs_client"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AudiobookShelf client not initialized",
        )

    try:
        is_valid = await app_state["abs_client"].validate_connection()
        if is_valid:
            return {"valid": True, "message": "Connected successfully"}
        else:
            return {
                "valid": False,
                "message": "Connection failed - check URL and API key",
            }
    except Exception as e:
        return {"valid": False, "message": f"Error: {str(e)}"}


@app.post("/api/validate/hardcovers")
async def validate_hardcovers():
    """Validate Hardcovers connection."""
    if not app_state["hardcovers_client"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hardcovers client not initialized",
        )

    try:
        is_valid = await app_state["hardcovers_client"].validate_connection()
        if is_valid:
            return {"valid": True, "message": "Connected successfully"}
        else:
            return {"valid": False, "message": "Invalid API key"}
    except Exception as e:
        return {"valid": False, "message": f"Error: {str(e)}"}


@app.post("/api/validate/storygraph")
async def validate_storygraph(auth_method: str = None, session_cookie: str = None, username: str = None, password: str = None):
    """Validate StoryGraph connection (supports both cookie and password auth)."""
    if not auth_method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auth_method is required (cookie or password)",
        )
    
    try:
        if auth_method == "cookie":
            if not session_cookie or not session_cookie.strip():
                return {"valid": False, "message": "Session cookie is required"}
            
            # Create temporary client with cookie
            temp_client = StoryGraphClient(session_cookie=session_cookie)
            is_valid = await temp_client.validate_connection()
            await temp_client.close()
            
            if is_valid:
                # Store the cookie in settings
                app_state["settings"].storygraph_session_cookie = session_cookie
                app_state["storygraph_client"] = StoryGraphClient(
                    session_cookie=session_cookie,
                    username=app_state["settings"].storygraph_username,
                    password=app_state["settings"].storygraph_password,
                )
                return {"valid": True, "message": "Cookie validated - read-only mode enabled"}
            else:
                return {"valid": False, "message": "Cookie validation failed - cookie may be expired"}
        
        elif auth_method == "password":
            if not username or not username.strip() or not password or not password.strip():
                return {"valid": False, "message": "Username and password are required"}
            
            # Create temporary client with credentials
            temp_client = StoryGraphClient(username=username, password=password)
            is_valid = await temp_client.validate_connection()
            await temp_client.close()
            
            if is_valid:
                # Store credentials in settings
                app_state["settings"].storygraph_username = username
                app_state["settings"].storygraph_password = password
                app_state["storygraph_client"] = StoryGraphClient(
                    session_cookie=app_state["settings"].storygraph_session_cookie,
                    username=username,
                    password=password,
                )
                return {"valid": True, "message": "Credentials validated - read+write mode enabled (requires storygraph-api library)"}
            else:
                return {"valid": False, "message": "Invalid username or password"}
        
        else:
            return {"valid": False, "message": "Invalid auth_method (use 'cookie' or 'password')"}
            
    except Exception as e:
        logger.error(f"Error validating StoryGraph: {e}")
        return {"valid": False, "message": f"Error: {str(e)}"}


@app.post("/api/setup/complete")
async def setup_complete():
    """Signal that setup wizard is complete and AudiobookShelf is configured."""
    if not can_run_sync(app_state["settings"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AudiobookShelf URL and API key must be configured before starting sync",
        )
    
    app_state["setup_complete"] = True
    logger.info("Setup marked as complete, triggering initial sync...")
    
    if app_state["scheduler"] and app_state["worker"]:
        try:
            # Check if scheduler is already running
            if app_state["scheduler"].scheduler.running:
                logger.info("Scheduler already running")
            else:
                # Create sync function wrapper
                async def periodic_sync_job():
                    """Periodic sync job wrapper."""
                    db = app_state["scheduler"].get_session()
                    try:
                        await app_state["worker"].run_periodic_sync(db)
                    finally:
                        db.close()
                
                # Add periodic sync job
                await app_state["scheduler"].add_periodic_sync_job(
                    sync_function=periodic_sync_job,
                    interval_minutes=app_state["settings"].sync_interval_minutes,
                    job_id="periodic_sync"
                )
                
                # Start scheduler
                await app_state["scheduler"].start()
                logger.info("Scheduler started")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start scheduler: {str(e)}",
            )
    
    return {"message": "Setup complete, sync scheduled"}


@app.get("/api/books/unmatched")
async def get_unmatched_books(db=Depends(get_db)):
    """Get all books that haven't been matched to platform IDs."""
    if not app_state["matcher"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Matcher not initialized",
        )
    
    try:
        unmatched = []
        
        # Get all books from AudiobookShelf
        libraries = await app_state["abs_client"].get_user_libraries()
        
        for library in libraries:
            library_id = library.get("id")
            items = await app_state["abs_client"].get_library_items(library_id)
            
            for item in items:
                # Check if book has platform mappings
                # For now, return all items (TODO: check database for mappings)
                book = {
                    "id": item.get("id"),
                    "title": item.get("title", "Unknown"),
                    "author": item.get("author", "Unknown"),
                    "isbn": item.get("isbn", ""),
                    "library_id": library_id,
                }
                unmatched.append(book)
        
        return unmatched
    except Exception as e:
        logger.error(f"Error getting unmatched books: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/api/books/match")
async def match_book(book_id: str, platform: str, platform_id: str, db=Depends(get_db)):
    """Manually match a book to a platform ID."""
    if not app_state["matcher"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Matcher not initialized",
        )
    
    if platform not in ["hardcovers", "storygraph"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid platform. Must be 'hardcovers' or 'storygraph'",
        )
    
    try:
        # TODO: Store mapping in database
        logger.info(f"Mapped book {book_id} to {platform}:{platform_id}")
        return {
            "message": "Book mapped successfully",
            "book_id": book_id,
            "platform": platform,
            "platform_id": platform_id,
        }
    except Exception as e:
        logger.error(f"Error matching book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.post("/api/sync/start")
async def start_sync():
    """Trigger an immediate sync instead of waiting for schedule."""
    if not app_state["scheduler"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scheduler not initialized",
        )
    
    try:
        logger.info("Manual sync triggered by user")
        # TODO: Implement actual sync trigger
        return {
            "message": "Sync started",
            "status": "in_progress",
        }
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )





@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main UI page."""
    html_file = Path(__file__).parent / "index.html"
    if html_file.exists():
        return html_file.read_text()
    return "<h1>AudioBook Sync</h1><p>UI not found</p>"


# ============================================================================
# Additional Routes
# ============================================================================


@app.get("/api/config/display")
async def get_config_display():
    """Get read-only configuration for display."""
    settings = app_state["settings"]
    return {
        "audiobookshelf_url": settings.audiobookshelf_url,
        "sync_interval_minutes": settings.sync_interval_minutes,
        "auto_match_on_first_run": settings.auto_match_on_first_run,
        "log_level": settings.log_level,
    }
