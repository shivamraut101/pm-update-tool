"""Sync projects, team members, and clients from the reference database on startup."""
import certifi
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorClient

from backend.config import settings
from backend.database import get_db


async def sync_from_reference_db():
    """Pull latest data from reference DB into PM tool DB."""
    if not settings.ref_mongodb_uri:
        print("[ref_sync] REF_MONGODB_URI not configured - skipping sync.")
        return

    print("[ref_sync] Starting sync from reference database...")

    kwargs = {}
    if settings.ref_mongodb_uri.startswith("mongodb+srv"):
        kwargs["tlsCAFile"] = certifi.where()

    ref_client = AsyncIOMotorClient(settings.ref_mongodb_uri, **kwargs)
    ref_db = ref_client[settings.ref_mongodb_db_name]
    pm_db = get_db()

    try:
        # ---- Sync Users -> Team Members ----
        ref_users = await ref_db.users.find().to_list(None)
        user_id_map = {}

        await pm_db.team_members.delete_many({})
        for user in ref_users:
            name = user.get("name", "Unknown")
            first_name = name.split()[0] if name else "Unknown"
            role_map = {"admin": "Admin", "dev": "Developer"}
            role = role_map.get(user.get("role", "dev"), "Developer")

            doc = {
                "name": name,
                "nickname": first_name,
                "aliases": [first_name.lower(), name.lower()],
                "role": role,
                "email": user.get("email", ""),
                "project_ids": [],
                "is_active": True,
                "ref_id": str(user["_id"]),
                "created_at": user.get("createdAt", datetime.now(UTC)),
            }
            result = await pm_db.team_members.insert_one(doc)
            user_id_map[str(user["_id"])] = str(result.inserted_id)

        print(f"[ref_sync] Synced {len(ref_users)} team members.")

        # ---- Sync Projects ----
        ref_projects = await ref_db.projects.find().to_list(None)

        await pm_db.projects.delete_many({})
        for proj in ref_projects:
            name = proj.get("name", "Unknown")
            team_ids = []
            for ref_member_id in proj.get("teamMembers", []):
                pm_id = user_id_map.get(str(ref_member_id))
                if pm_id:
                    team_ids.append(pm_id)

            words = name.split()
            if len(words) >= 2:
                code = "".join(w[0].upper() for w in words[:3])
            else:
                code = name[:4].upper()

            doc = {
                "name": name,
                "code": code,
                "client_name": "",
                "description": proj.get("description", ""),
                "status": proj.get("status", "active"),
                "health": proj.get("health", "on_track"),
                "tech_stack": proj.get("techStack", []),
                "repository_url": proj.get("repositoryUrl", ""),
                "team_member_ids": team_ids,
                "ref_id": str(proj["_id"]),
                "created_at": proj.get("createdAt", datetime.now(UTC)),
                "updated_at": proj.get("updatedAt", datetime.now(UTC)),
            }
            await pm_db.projects.insert_one(doc)

        print(f"[ref_sync] Synced {len(ref_projects)} projects.")

        # ---- Sync Clients ----
        ref_clients = await ref_db.clients.find().to_list(None)

        await pm_db.clients.delete_many({})
        for cl in ref_clients:
            doc = {
                "name": cl.get("name", "Unknown"),
                "company_name": cl.get("companyName", ""),
                "email": cl.get("email", ""),
                "phone": cl.get("phone", ""),
                "status": cl.get("status", "active"),
                "type": cl.get("type", "company"),
                "notes": cl.get("notes", ""),
                "ref_id": str(cl["_id"]),
                "created_at": cl.get("createdAt", datetime.now(UTC)),
            }
            await pm_db.clients.insert_one(doc)

        print(f"[ref_sync] Synced {len(ref_clients)} clients.")

        # ---- Update team member project_ids ----
        from bson import ObjectId
        all_projects = await pm_db.projects.find().to_list(None)
        for proj in all_projects:
            for member_id in proj.get("team_member_ids", []):
                await pm_db.team_members.update_one(
                    {"_id": ObjectId(member_id)},
                    {"$addToSet": {"project_ids": str(proj["_id"])}},
                )

        # ---- Settings (only create if missing) ----
        existing = await pm_db.settings.find_one({"_id": "config"})
        if not existing:
            await pm_db.settings.insert_one({
                "_id": "config",
                "daily_brief_time": "18:00",
                "weekly_report_day": "friday",
                "weekly_report_time": "18:00",
                "timezone": "Asia/Kolkata",
                "updated_at": datetime.now(UTC),
            })

        print("[ref_sync] Sync complete!")

    except Exception as e:
        print(f"[ref_sync] Error during sync: {e}")
    finally:
        ref_client.close()
