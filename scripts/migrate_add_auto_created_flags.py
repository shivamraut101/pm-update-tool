"""Migration script: Add auto_created flags to existing projects and team members.

Run this once to migrate existing data:
    python -m scripts.migrate_add_auto_created_flags
"""
import asyncio
from backend.database import connect_db, close_db, get_db


async def migrate():
    """Add auto_created=False to all existing projects/team members."""
    await connect_db()
    db = get_db()

    print("[migrate] Adding auto_created flags to existing projects...")
    result_projects = await db.projects.update_many(
        {"auto_created": {"$exists": False}},
        {"$set": {"auto_created": False, "needs_reference_sync": False}}
    )
    print(f"[migrate] Updated {result_projects.modified_count} projects")

    print("[migrate] Adding auto_created flags to existing team members...")
    result_members = await db.team_members.update_many(
        {"auto_created": {"$exists": False}},
        {"$set": {"auto_created": False, "needs_reference_sync": False}}
    )
    print(f"[migrate] Updated {result_members.modified_count} team members")

    await close_db()
    print("[migrate] Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
