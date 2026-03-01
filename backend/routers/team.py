from fastapi import APIRouter, HTTPException
from bson import ObjectId

from backend.database import get_db

router = APIRouter()


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
