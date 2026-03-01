from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from backend.config import settings

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    # Create indexes
    await db.projects.create_index("name", unique=True)
    await db.projects.create_index("status")
    await db.team_members.create_index([("name", 1), ("nickname", 1)])
    await db.updates.create_index("date")
    await db.updates.create_index("created_at")
    await db.reports.create_index([("type", 1), ("date", 1)], unique=True)
    await db.reminders.create_index([("is_dismissed", 1), ("trigger_time", 1)])


async def close_db():
    global client
    if client:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    return db
