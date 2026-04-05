from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.link_service import LinkService

router = APIRouter()
redirect_router = APIRouter()

@router.post("")
def create_short_link(original_url: str, custom_code: str = None, ttl: int = None, db: Session = Depends(get_db)):
    # TODO: implement link creation
    pass

@router.get("/{short_code}")
def get_link_info(short_code: str, db: Session = Depends(get_db)):
    # TODO: implement get link stats
    pass

@router.delete("/{short_code}")
def delete_link(short_code: str, db: Session = Depends(get_db)):
    # TODO: implement link deletion
    pass

@redirect_router.get("/s/{short_code}")
def redirect_to_original(short_code: str, db: Session = Depends(get_db)):
    # TODO: implement redirect with 302
    pass
