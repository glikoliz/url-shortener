from sqlalchemy.orm import Session
from app.models.link import Link


class LinkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, link: Link) -> Link:
        # TODO: implement
        pass

    def get_by_code(self, short_code: str) -> Link:
        # TODO: implement
        pass

    def delete(self, link: Link):
        # TODO: implement
        pass

    def increment_clicks(self, link_id: int):
        # TODO: implement
        pass
