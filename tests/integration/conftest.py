import os

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from app.database import Base, get_db
from app.main import app
from app.redis import get_redis


@pytest.fixture(autouse=True)
def mock_resolve_url():
    with patch(
        "app.services.link_service._resolve_final_url", new_callable=AsyncMock
    ) as m:
        m.side_effect = lambda url: url if url.endswith("/") else url + "/"
        yield m


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        yield async_url


@pytest.fixture(scope="session")
def redis_url():
    with DockerContainer("redis:7-alpine").with_exposed_ports(6379) as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_url):
    engine = create_async_engine(postgres_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clear_database(db_engine, redis_url):
    async with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE;"))

    from redis.asyncio import Redis

    test_redis = Redis.from_url(redis_url)
    await test_redis.flushdb()
    await test_redis.aclose()


@pytest_asyncio.fixture
async def client(db_engine, redis_url):
    TestingSessionLocal = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    from redis.asyncio import Redis

    from app.limiter import limiter_manager

    test_redis = Redis.from_url(redis_url, decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: test_redis

    await limiter_manager.init_limiter(
        "auth:register", test_redis, requests=3, seconds=60
    )
    await limiter_manager.init_limiter("auth:login", test_redis, requests=5, seconds=60)
    await limiter_manager.init_limiter(
        "links:create", test_redis, requests=10, seconds=60
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_redis.aclose()
