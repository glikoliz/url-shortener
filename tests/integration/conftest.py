import os

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        yield async_url


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_url):
    engine = create_async_engine(postgres_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clear_database(db_engine):
    async with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE;"))


@pytest_asyncio.fixture
async def client(db_engine):
    TestingSessionLocal = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
