from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import os
import uuid

from backend.database import get_db
from backend.services.ai_parser import parse_update
from backend.services.screenshot_processor import process_screenshots
from backend.utils.date_helpers import today_str

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


@router.post("/updates")
async def create_update(
    raw_text: str = Form(""),
    source: str = Form("web"),
    screenshots: List[UploadFile] = File(default=[]),
):
    """Submit a new update with optional screenshots."""
    db = get_db()
    date = today_str()

    # Save uploaded screenshots
    screenshot_paths = []
    if screenshots:
        date_dir = os.path.join(UPLOAD_DIR, date)
        os.makedirs(date_dir, exist_ok=True)
        for file in screenshots:
            if file.filename and file.size and file.size > 0:
                ext = os.path.splitext(file.filename)[1] or ".png"
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(date_dir, filename)
                content = await file.read()
                with open(filepath, "wb") as f:
                    f.write(content)
                screenshot_paths.append(f"uploads/{date}/{filename}")

    # Process screenshots and parse with AI
    screenshot_text = ""
    if screenshot_paths:
        full_paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", path)
            for path in screenshot_paths
        ]
        screenshot_text = await process_screenshots(full_paths)

    # Combine text and screenshot extractions for AI parsing
    combined_text = raw_text
    if screenshot_text:
        combined_text += f"\n\n[Screenshot content]: {screenshot_text}"

    # Fetch projects and team members for context
    projects = await db.projects.find({"status": "active"}).to_list(None)
    team_members = await db.team_members.find({"is_active": True}).to_list(None)

    # Parse with AI
    parsed, confidence = await parse_update(combined_text, projects, team_members)

    # Build update document
    update_doc = {
        "raw_text": raw_text,
        "source": source,
        "has_screenshot": len(screenshot_paths) > 0,
        "screenshot_paths": screenshot_paths,
        "screenshot_extracted_text": screenshot_text,
        "parsed": parsed,
        "ai_confidence": confidence,
        "created_at": datetime.utcnow(),
        "date": date,
    }

    result = await db.updates.insert_one(update_doc)
    update_doc["_id"] = str(result.inserted_id)

    return update_doc


@router.get("/updates")
async def list_updates(
    date: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
):
    """List updates with optional filtering."""
    db = get_db()
    query = {}
    if date:
        query["date"] = date
    if project_id:
        query["parsed.team_updates.project_id"] = project_id

    cursor = db.updates.find(query).sort("created_at", -1).skip(skip).limit(limit)
    updates = await cursor.to_list(length=limit)

    for u in updates:
        u["_id"] = str(u["_id"])

    return updates


@router.get("/updates/{update_id}")
async def get_update(update_id: str):
    """Get a single update by ID."""
    db = get_db()
    update = await db.updates.find_one({"_id": ObjectId(update_id)})
    if not update:
        raise HTTPException(status_code=404, detail="Update not found")
    update["_id"] = str(update["_id"])
    return update


@router.put("/updates/{update_id}")
async def edit_update(update_id: str, parsed: dict):
    """Edit the parsed content of an update (correct AI mistakes)."""
    db = get_db()
    result = await db.updates.update_one(
        {"_id": ObjectId(update_id)},
        {"$set": {"parsed": parsed}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Update not found")
    return {"status": "updated"}


@router.delete("/updates/{update_id}")
async def delete_update(update_id: str):
    """Delete an update."""
    db = get_db()
    result = await db.updates.delete_one({"_id": ObjectId(update_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Update not found")
    return {"status": "deleted"}
