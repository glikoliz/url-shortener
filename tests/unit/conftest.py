from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.link import Link
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.link_service import LinkService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def auth_service(mock_db):
    service = AuthService(mock_db)
    service.user_repo = MagicMock()
    service.user_repo.get_by_email = AsyncMock()
    service.user_repo.get_by_id = AsyncMock()
    service.user_repo.create = AsyncMock()
    return service


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.get.return_value = None
    return mock


@pytest.fixture
def link_service(mock_db, mock_redis):
    service = LinkService(mock_db, redis=mock_redis)
    service.link_repo = MagicMock()
    service.link_repo.get_by_code = AsyncMock()
    service.link_repo.create = AsyncMock()
    service.link_repo.delete = AsyncMock()
    service.link_repo.increment_clicks = AsyncMock()
    service.link_repo.increment_clicks_by_code = AsyncMock()
    return service


@pytest.fixture
def mock_user():
    def _make(
        id: int = 1,
        email: str = "test@example.com",
        password_hash: str = "hashed_password",
        is_active: bool = True,
    ) -> User:
        user = User(
            id=id,
            email=email,
            password_hash=password_hash,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
        )
        return user

    return _make


@pytest.fixture
def mock_link():
    def _make(
        id: int = 1,
        user_id: int = 1,
        original_url: str = "https://google.com",
        short_code: str = "abc123",
        clicks: int = 0,
        expires_at=None,
    ) -> Link:
        link = Link(
            id=id,
            user_id=user_id,
            original_url=original_url,
            short_code=short_code,
            clicks=clicks,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        return link

    return _make
