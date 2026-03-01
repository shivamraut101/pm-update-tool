"""Sync projects, team members, and clients from the reference database."""
import asyncio
import certifi
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

# PM tool database (read-write)
PM_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
PM_DB = os.getenv("MONGODB_DB_NAME", "pm_update_tool")

# Reference database (read-only)
REF_URI = os.getenv("REF_MONGODB_URI", "")
REF_DB = os.getenv("REF_MONGODB_DB_NAME", "live")

# TLS CA file for Atlas connections
TLS_CA = certifi.where()


async def sync():
    if not REF_URI:
        print("ERROR: REF_MONGODB_URI not set in .env - cannot sync.")
        return

    ref_client = AsyncIOMotorClient(REF_URI, tlsCAFile=TLS_CA)
    ref_db = ref_client[REF_DB]

    pm_client = AsyncIOMotorClient(PM_URI, tlsCAFile=TLS_CA)
    pm_db = pm_client[PM_DB]

    print("Connected to both databases.\n")

    # ---- Sync Users -> Team Members ----
    print("=== Syncing Team Members ===")
    ref_users = await ref_db.users.find().to_list(None)
    user_id_map = {}  # ref ObjectId -> pm ObjectId

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
            "created_at": user.get("createdAt", datetime.utcnow()),
        }
        result = await pm_db.team_members.insert_one(doc)
        user_id_map[str(user["_id"])] = str(result.inserted_id)
        print(f"  + {name} ({role}) -> {result.inserted_id}")

    print(f"Synced {len(ref_users)} team members.\n")

    # ---- Sync Projects ----
    print("=== Syncing Projects ===")
    ref_projects = await ref_db.projects.find().to_list(None)

    await pm_db.projects.delete_many({})
    for proj in ref_projects:
        name = proj.get("name", "Unknown")
        # Map team member ref IDs to PM tool IDs
        team_ids = []
        for ref_member_id in proj.get("teamMembers", []):
            pm_id = user_id_map.get(str(ref_member_id))
            if pm_id:
                team_ids.append(pm_id)

        # Generate a short code from name
        words = name.split()
        if len(words) >= 2:
            code = "".join(w[0].upper() for w in words[:3])
        else:
            code = name[:4].upper()

        status = proj.get("status", "active")
        doc = {
            "name": name,
            "code": code,
            "client_name": "",
            "description": proj.get("description", ""),
            "status": status,
            "health": proj.get("health", "on_track"),
            "tech_stack": proj.get("techStack", []),
            "repository_url": proj.get("repositoryUrl", ""),
            "team_member_ids": team_ids,
            "ref_id": str(proj["_id"]),
            "created_at": proj.get("createdAt", datetime.utcnow()),
            "updated_at": proj.get("updatedAt", datetime.utcnow()),
        }
        result = await pm_db.projects.insert_one(doc)
        print(f"  + {name} [{status}] ({len(team_ids)} members) -> {result.inserted_id}")

    print(f"Synced {len(ref_projects)} projects.\n")

    # ---- Sync Clients ----
    print("=== Syncing Clients ===")
    ref_clients = await ref_db.clients.find().to_list(None)

    # Store clients in a clients collection
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
            "created_at": cl.get("createdAt", datetime.utcnow()),
        }
        result = await pm_db.clients.insert_one(doc)
        print(f"  + {doc['name']} ({doc['email']}) -> {result.inserted_id}")

    print(f"Synced {len(ref_clients)} clients.\n")

    # ---- Update team member project_ids ----
    print("=== Updating team member project assignments ===")
    all_projects = await pm_db.projects.find().to_list(None)
    for proj in all_projects:
        for member_id in proj.get("team_member_ids", []):
            await pm_db.team_members.update_one(
                {"_id": __import__("bson").ObjectId(member_id)},
                {"$addToSet": {"project_ids": str(proj["_id"])}},
            )
    print("Done.\n")

    # ---- Settings ----
    existing_settings = await pm_db.settings.find_one({"_id": "config"})
    if not existing_settings:
        await pm_db.settings.insert_one({
            "_id": "config",
            "daily_brief_time": "18:00",
            "weekly_report_day": "friday",
            "weekly_report_time": "18:00",
            "timezone": "Asia/Kolkata",
            "updated_at": datetime.utcnow(),
        })
        print("Settings initialized.")
    else:
        print("Settings already exist, skipping.")

    ref_client.close()
    pm_client.close()
    print("\nSync complete!")


if __name__ == "__main__":
    asyncio.run(sync())
