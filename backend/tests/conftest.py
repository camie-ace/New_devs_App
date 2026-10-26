"""Integration tests use isolated PostgreSQL schemas; supplied sample data stays unchanged."""
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import dashboard, login
from app.core import auth
from app.core.database_pool import DatabasePool
from app.services import cache, reservations


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.writes = []

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.writes.append((key, ttl, value))


@pytest.fixture
def memory_cache(monkeypatch):
    client = MemoryRedis()
    monkeypatch.setattr(cache, "redis_client", client)
    return client


@pytest_asyncio.fixture
async def db(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    schema = "test_" + uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": f"{schema},public"}})
    async with engine.begin() as connection:
        raw = await connection.get_raw_connection()
        root = Path(__file__).resolve().parents[2] / "database"
        for filename in ("schema.sql", "seed.sql"):
            await raw.driver_connection.execute((root / filename).read_text())
    pool = DatabasePool()
    pool.engine = engine
    pool.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(reservations, "db_pool", pool)
    try:
        yield pool
    finally:
        await pool.close()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest_asyncio.fixture
async def api(db, memory_cache):
    auth.clear_auth_cache()
    app = FastAPI()
    app.include_router(login.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
    auth.clear_auth_cache()


async def login_as(client, tenant="a"):
    credentials = {
        "a": ("sunset@propertyflow.com", "client_a_2024"),
        "b": ("ocean@propertyflow.com", "client_b_2024"),
    }
    email, password = credentials[tenant]
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}
