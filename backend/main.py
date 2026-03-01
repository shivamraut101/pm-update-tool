from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from backend.database import connect_db, close_db
from backend.routers import updates, projects, team, reports, reminders, whatsapp, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_db()

    # Start scheduler (imported here to avoid circular imports)
    from backend.services.scheduler import start_scheduler
    await start_scheduler()

    yield

    # Shutdown
    from backend.services.scheduler import stop_scheduler
    stop_scheduler()
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

# Include page routers
app.include_router(dashboard.router, tags=["Pages"])
