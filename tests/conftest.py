"""Test fixtures for PM Update Tool."""
import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database and clean up after."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["pm_update_tool_test"]
    yield db
    # Cleanup
    await client.drop_database("pm_update_tool_test")
    client.close()
