"""Client management routes."""
from fastapi import APIRouter, HTTPException
from backend.database import get_db
from backend.models.client import ClientCreate, ClientResponse
from datetime import datetime

router = APIRouter()


@router.get("/api/clients", response_model=list[ClientResponse])
async def get_clients():
    """List all clients with their associated projects."""
    db = get_db()
    clients = await db.clients.find().sort("created_at", -1).to_list(None)
    for c in clients:
        c["_id"] = str(c["_id"])
    return clients


@router.post("/api/clients", response_model=ClientResponse)
async def create_client(client: ClientCreate):
    """Manually create a client."""
    db = get_db()

    # Check for duplicate (case-insensitive)
    existing = await db.clients.find_one(
        {"name": {"$regex": f"^{client.name}$", "$options": "i"}}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Client with this name already exists")

    client_doc = {
        "name": client.name,
        "project_ids": client.project_ids,
        "contact_email": client.contact_email,
        "auto_created": False,  # Manually created, not auto-discovered
        "created_at": datetime.utcnow(),
    }
    result = await db.clients.insert_one(client_doc)
    client_doc["_id"] = str(result.inserted_id)
    return client_doc


@router.put("/api/clients/{client_id}/projects/{project_id}")
async def link_client_to_project(client_id: str, project_id: str):
    """Associate a client with a project."""
    db = get_db()

    # Verify both exist
    client = await db.clients.find_one({"_id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Link client to project
    await db.clients.update_one(
        {"_id": client_id},
        {"$addToSet": {"project_ids": project_id}}
    )

    # Link project to client
    await db.projects.update_one(
        {"_id": project_id},
        {"$set": {"client_id": client_id, "client_name": client["name"]}}
    )

    return {"status": "linked", "client": client["name"], "project": project["name"]}


@router.delete("/api/clients/{client_id}")
async def delete_client(client_id: str):
    """Delete a client and unlink from all projects."""
    db = get_db()

    client = await db.clients.find_one({"_id": client_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Unlink from all projects
    await db.projects.update_many(
        {"client_id": client_id},
        {"$set": {"client_id": None, "client_name": ""}}
    )

    # Delete client
    await db.clients.delete_one({"_id": client_id})

    return {"status": "deleted", "client": client["name"]}
