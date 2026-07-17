import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.models import Base
from app.core.config import get_settings

async def init_db():
    settings = get_settings()
    print(f"Initializing database using URL: {settings.async_database_url}")
    engine = create_async_engine(settings.async_database_url, echo=True)
    async with engine.begin() as conn:
        print("Dropping existing tables (if any)...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
