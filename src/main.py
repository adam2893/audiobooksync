"""Main application entry point."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uvicorn
from src.logger import setup_logger
from src.config import get_settings
from src.ui.app import app

logger = setup_logger("main")


async def main():
    """Main application entry point."""
    try:
        settings = get_settings()
        
        logger.info(f"Starting AudioBook Sync on {settings.web_ui_host}:{settings.web_ui_port}")
        
        config = uvicorn.Config(
            app,
            host=settings.web_ui_host,
            port=settings.web_ui_port,
            log_level=settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        
        await server.serve()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
