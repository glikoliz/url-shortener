from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register")
def register(email: str, password: str, db: Session = Depends(get_db)):
    # TODO: implement registration
    pass

@router.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    # TODO: implement login
    pass

@router.post("/logout")
def logout():
    # TODO: implement logout
    pass
