from fastapi import FastAPI
from app.api import auth, links

app = FastAPI(title="URL Shortener API", version="1.0.0")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(links.router, prefix="/api/v1/links", tags=["links"])
app.include_router(links.redirect_router, tags=["redirect"])

@app.get("/")
def root():
    return {"message": "URL Shortener API"}
