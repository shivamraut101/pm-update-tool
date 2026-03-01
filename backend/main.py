from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import os

from backend.config import settings
from backend.database import connect_db, close_db
from backend.routers import updates, projects, team, reports, reminders, whatsapp, dashboard
from backend.routers import telegram as telegram_router


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
                print(f"[main] Telegram webhook mode (POST {settings.app_url}/api/telegram/webhook)")
            else:
                print("[main] Webhook setup failed — falling back to polling")
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
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include API routers
app.include_router(updates.router, prefix="/api", tags=["Updates"])
app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(team.router, prefix="/api", tags=["Team"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(reminders.router, prefix="/api", tags=["Reminders"])
app.include_router(whatsapp.router, prefix="/api", tags=["WhatsApp"])
app.include_router(telegram_router.router, prefix="/api", tags=["Telegram"])

# Include page routers
app.include_router(dashboard.router, tags=["Pages"])
