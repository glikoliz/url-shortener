from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository

class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)
    
    def register(self, email: str, password: str):
        # TODO: hash password, create user
        pass
    
    def login(self, email: str, password: str):
        # TODO: verify password, generate JWT
        pass
    
    def verify_token(self, token: str):
        # TODO: decode and verify JWT
        pass
