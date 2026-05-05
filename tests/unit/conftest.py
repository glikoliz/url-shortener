from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.link import Link
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.link_service import LinkService


@pytest.fixture
def mock_uow():
    uow = MagicMock()
    # Mock context manager
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)

    # Mock repositories
    uow.users = MagicMock()
    uow.users.get_by_email = AsyncMock()
    uow.users.get_by_id = AsyncMock()
    uow.users.create = AsyncMock()

    uow.links = MagicMock()
    uow.links.get_by_code = AsyncMock()
    uow.links.create = AsyncMock()
    uow.links.delete = AsyncMock()
    uow.links.increment_clicks = AsyncMock()
    uow.links.increment_clicks_by_code = AsyncMock()
    uow.links.get_by_user_id = AsyncMock()

    uow.clicks = MagicMock()
    uow.clicks.create = AsyncMock()
    uow.clicks.get_by_link_id = AsyncMock(return_value=([], 0))
    uow.clicks.get_aggregated_stats = AsyncMock(
        return_value={
            "total_clicks": 0,
            "unique_clicks": 0,
            "unique_ips": 0,
            "granularity": "day",
            "clicks_over_time": [],
            "clicks_by_day": [],
            "top_referers": [],
            "top_countries": [],
        }
    )

    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.session = MagicMock()
    uow.session.refresh = AsyncMock()
    uow.session.execute = AsyncMock()

    return uow


@pytest.fixture
def auth_service(mock_uow):
    service = AuthService(mock_uow)
    # Add shortcuts for tests that access repositories directly on the service
    service.user_repo = mock_uow.users
    return service


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.get.return_value = None
    mock.exists.return_value = False
    mock.set.return_value = True
    mock.incr.return_value = 1
    return mock


@pytest.fixture
def link_service(mock_uow, mock_redis):
    service = LinkService(mock_uow, redis=mock_redis)
    # Add shortcuts for tests that access repositories directly on the service
    service.link_repo = mock_uow.links
    service.click_repo = mock_uow.clicks
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
