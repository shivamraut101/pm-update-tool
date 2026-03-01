"""Seed the database with sample projects and team members."""
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "pm_update_tool"

SAMPLE_PROJECTS = [
    {
        "name": "Project Alpha",
        "code": "ALPHA",
        "client_name": "Acme Corp",
        "description": "E-commerce platform rebuild with modern tech stack",
        "status": "active",
        "team_member_ids": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "Project Beta",
        "code": "BETA",
        "client_name": "TechFlow Inc",
        "description": "Internal dashboard and analytics tool",
        "status": "active",
        "team_member_ids": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "Project Gamma",
        "code": "GAMMA",
        "client_name": "StartupXYZ",
        "description": "Mobile app MVP development",
        "status": "active",
        "team_member_ids": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
]

SAMPLE_TEAM = [
    {
        "name": "Rahul Sharma",
        "nickname": "Rahul",
        "aliases": ["RS", "rahul"],
        "role": "Frontend Developer",
        "email": "rahul@example.com",
        "project_ids": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    },
    {
        "name": "Priya Patel",
        "nickname": "Priya",
        "aliases": ["PP", "priya"],
        "role": "Backend Developer",
        "email": "priya@example.com",
        "project_ids": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    },
    {
        "name": "Amit Kumar",
        "nickname": "Amit",
        "aliases": ["AK", "amit"],
        "role": "Full Stack Developer",
        "email": "amit@example.com",
        "project_ids": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    },
    {
        "name": "Sneha Gupta",
        "nickname": "Sneha",
        "aliases": ["SG", "sneha"],
        "role": "QA Engineer",
        "email": "sneha@example.com",
        "project_ids": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    },
    {
        "name": "Vikram Singh",
        "nickname": "Vikram",
        "aliases": ["VS", "vikram"],
        "role": "DevOps Engineer",
        "email": "vikram@example.com",
        "project_ids": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    # Clear existing data
    await db.projects.delete_many({})
    await db.team_members.delete_many({})

    # Insert projects
    result = await db.projects.insert_many(SAMPLE_PROJECTS)
    project_ids = result.inserted_ids
    print(f"Inserted {len(project_ids)} projects")

    # Assign projects to team members
    SAMPLE_TEAM[0]["project_ids"] = [str(project_ids[0])]  # Rahul -> Alpha
    SAMPLE_TEAM[1]["project_ids"] = [str(project_ids[0])]  # Priya -> Alpha
    SAMPLE_TEAM[2]["project_ids"] = [str(project_ids[1])]  # Amit -> Beta
    SAMPLE_TEAM[3]["project_ids"] = [str(project_ids[0]), str(project_ids[1])]  # Sneha -> Alpha, Beta
    SAMPLE_TEAM[4]["project_ids"] = [str(project_ids[2])]  # Vikram -> Gamma

    result = await db.team_members.insert_many(SAMPLE_TEAM)
    print(f"Inserted {len(result.inserted_ids)} team members")

    # Create initial settings doc
    await db.settings.delete_many({})
    await db.settings.insert_one({
        "_id": "config",
        "daily_brief_time": "18:00",
        "weekly_report_day": "friday",
        "weekly_report_time": "18:00",
        "timezone": "Asia/Kolkata",
        "updated_at": datetime.utcnow(),
    })
    print("Settings initialized")

    client.close()
    print("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
