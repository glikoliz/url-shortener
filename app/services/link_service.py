from sqlalchemy.orm import Session
from app.repositories.link_repository import LinkRepository


class LinkService:
    def __init__(self, db: Session):
        self.link_repo = LinkRepository(db)

    def shorten_url(
        self,
        original_url: str,
        custom_code: str = None,
        ttl: int = None,
        user_id: int = None,
    ):
        # TODO: validate URL, generate short_code, create link
        pass

    def resolve_link(self, short_code: str):
        # TODO: get link, check expiration, increment clicks, return original_url
        pass

    def get_stats(self, short_code: str):
        # TODO: return link statistics
        pass

    def delete_link(self, short_code: str, user_id: int):
        # TODO: verify ownership, delete link
        pass
