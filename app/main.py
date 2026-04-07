from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api import auth, links
from app.database import get_db

app = FastAPI(title="URL Shortener API", version="1.0.0")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(links.router, prefix="/api/v1/links", tags=["links"])
app.include_router(links.redirect_router, tags=["redirect"])


@app.get("/")
def root():
    return {"message": "URL Shortener API"}


@app.get("/ping", tags=["healthcheck"])
async def ping_db(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected", "result": result.scalar()}
    except Exception as e:
        return {"status": "error", "db": "disconnected", "detail": str(e)}
