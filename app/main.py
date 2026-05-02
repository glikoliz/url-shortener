from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import auth, links
from app.database import engine, get_db
from app.limiter import limiter_manager
from app.redis import close_redis, get_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await init_redis()
    await limiter_manager.init_limiter("auth:register", redis, requests=3, seconds=60)
    await limiter_manager.init_limiter("auth:login", redis, requests=5, seconds=60)
    await limiter_manager.init_limiter("links:create", redis, requests=10, seconds=60)
    await limiter_manager.init_limiter("links:redirect", redis, requests=5, seconds=60)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title="URL Shortener API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(links.router, prefix="/api/v1/links", tags=["links"])
app.include_router(links.redirect_router, tags=["redirect"])


@app.get("/")
def root():
    return {"message": "URL Shortener API"}


@app.get("/ping", tags=["healthcheck"])
async def ping(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    result = {}

    try:
        await db.execute(text("SELECT 1"))
        result["db"] = "connected"
    except Exception as e:
        result["db"] = f"error: {e}"

    try:
        await redis.ping()
        result["redis"] = "connected"
    except Exception as e:
        result["redis"] = f"error: {e}"

    all_ok = all("error" not in v for v in result.values())
    result["status"] = "ok" if all_ok else "degraded"
    return result
