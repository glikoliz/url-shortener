from sqlalchemy.orm import Session
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, email: str, password_hash: str) -> User:
        # TODO: implement
        pass

    def get_by_email(self, email: str) -> User:
        # TODO: implement
        pass

    def get_by_id(self, user_id: int) -> User:
        # TODO: implement
        pass
