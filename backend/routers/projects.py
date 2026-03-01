from fastapi import APIRouter, HTTPException
from bson import ObjectId

from backend.database import get_db

router = APIRouter()


@router.get("/projects")
async def list_projects(status: str = None):
    """List all projects, optionally filtered by status."""
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    projects = await db.projects.find(query).sort("name", 1).to_list(None)
    for p in projects:
        p["_id"] = str(p["_id"])
    return projects


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a single project by ID."""
    db = get_db()
    project = await db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["_id"] = str(project["_id"])
    return project
