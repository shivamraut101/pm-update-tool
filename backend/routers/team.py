from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from backend.database import get_db
from backend.models.team_member import TeamMemberCreate, TeamMemberUpdate

router = APIRouter()


@router.post("/team")
async def create_team_member(member: TeamMemberCreate):
    """Add a new team member."""
    db = get_db()
    doc = {
        **member.model_dump(),
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    # Auto-populate nickname if not provided
    if not doc["nickname"]:
        doc["nickname"] = doc["name"].split()[0]
    result = await db.team_members.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.get("/team")
async def list_team_members(active_only: bool = True):
    """List team members."""
    db = get_db()
    query = {"is_active": True} if active_only else {}
    members = await db.team_members.find(query).sort("name", 1).to_list(None)
    for m in members:
        m["_id"] = str(m["_id"])
    return members


@router.get("/team/{member_id}")
async def get_team_member(member_id: str):
    """Get a single team member."""
    db = get_db()
    member = await db.team_members.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    member["_id"] = str(member["_id"])
    return member


@router.put("/team/{member_id}")
async def update_team_member(member_id: str, update: TeamMemberUpdate):
    """Update a team member."""
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"status": "updated"}


@router.delete("/team/{member_id}")
async def deactivate_team_member(member_id: str):
    """Deactivate a team member (soft delete)."""
    db = get_db()
    result = await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"is_active": False}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"status": "deactivated"}
