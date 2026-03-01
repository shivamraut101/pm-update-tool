from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from backend.database import get_db
from backend.models.project import ProjectCreate, ProjectUpdate

router = APIRouter()


@router.post("/projects")
async def create_project(project: ProjectCreate):
    """Create a new project."""
    db = get_db()
    doc = {
        **project.model_dump(),
        "team_member_ids": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    try:
        result = await db.projects.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Project name already exists")
    doc["_id"] = str(result.inserted_id)
    return doc


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


@router.put("/projects/{project_id}")
async def update_project(project_id: str, update: ProjectUpdate):
    """Update a project."""
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "updated"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Soft-delete (archive) a project by setting status to archived."""
    db = get_db()
    result = await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": "archived", "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "archived"}
