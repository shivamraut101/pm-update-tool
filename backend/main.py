from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import time

from backend.config import settings
from backend.database import connect_db, close_db
from backend.routers import updates, projects, team, reports, reminders, dashboard, clients
from backend.routers import telegram as telegram_router
from backend.utils.logger import setup_logging, get_logger

# Initialize logging
setup_logging(level="INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_db()

    # Sync from reference database
    from backend.services.ref_sync import sync_from_reference_db
    await sync_from_reference_db()

    # Start scheduler
    from backend.services.scheduler import start_scheduler
    await start_scheduler()

    # Configure Telegram bot
    from backend.services.telegram_bot import (
        configure_telegram, start_polling, setup_webhook,
    )
    if settings.telegram_bot_token:
        configure_telegram(settings.telegram_bot_token, settings.telegram_chat_id)

        if settings.app_url:
            # Cloud deployment — register webhook so Telegram pushes to us
            ok = await setup_webhook(settings.app_url)
            if ok:
                logger.info(f"Telegram webhook mode (POST {settings.app_url}/api/telegram/webhook)")
            else:
                logger.warning("Webhook setup failed — falling back to polling")
                asyncio.create_task(start_polling())
        else:
            # Local development — use long-polling
            asyncio.create_task(start_polling())

    yield

    # Shutdown
    from backend.services.scheduler import stop_scheduler
    from backend.services.telegram_bot import stop_polling, remove_webhook
    stop_scheduler()
    stop_polling()
    if settings.app_url:
        await remove_webhook()
    await close_db()


app = FastAPI(
    title="PM Update Tool",
    description="Project Management Update & Reporting Tool",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing information."""
    start_time = time.time()

    # Log incoming request
    logger.info(f"→ {request.method} {request.url.path} | Client: {request.client.host if request.client else 'unknown'}")

    try:
        # Process request
        response = await call_next(request)

        # Log response with timing
        duration = (time.time() - start_time) * 1000
        logger.info(f"← {request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration:.2f}ms")

        return response
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"✗ {request.method} {request.url.path} | Error: {str(e)} | Duration: {duration:.2f}ms")
        raise

# Mount uploads directory for screenshots
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include API routers (all under /api prefix)
app.include_router(updates.router, prefix="/api", tags=["Updates"])
app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(team.router, prefix="/api", tags=["Team"])
app.include_router(clients.router, prefix="/api", tags=["Clients"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(reminders.router, prefix="/api", tags=["Reminders"])
app.include_router(telegram_router.router, prefix="/api", tags=["Telegram"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])

# Serve React SPA in production (after `npm run build`)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        """Serve React SPA for all non-API routes."""
        # Try to serve the exact file first (e.g., favicon.ico, vite.svg)
        file_path = frontend_dist / path
        if path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for client-side routing
        return FileResponse(str(frontend_dist / "index.html"))
