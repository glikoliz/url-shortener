from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.link import Link
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.link_service import LinkService


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()

    # Setup execute to return a mock result object
    execute_result = MagicMock()
    row = MagicMock()
    row.min_t = datetime.now(timezone.utc)
    row.max_t = datetime.now(timezone.utc)
    execute_result.one.return_value = row
    execute_result.scalar_one_or_none.return_value = None
    execute_result.scalar_one.return_value = 1
    execute_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(return_value=execute_result)
    return db


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
    link_repo = MagicMock()
    link_repo.get_by_code = AsyncMock()
    link_repo.create = AsyncMock()
    link_repo.delete = AsyncMock()
    link_repo.increment_clicks = AsyncMock()
    link_repo.increment_clicks_by_code = AsyncMock()
    link_repo.get_by_user_id = AsyncMock()

    click_repo = MagicMock()
    click_repo.create = AsyncMock()
    click_repo.get_by_link_id = AsyncMock(return_value=([], 0))
    click_repo.get_aggregated_stats = AsyncMock(
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

    service = LinkService(
        mock_db, redis=mock_redis, link_repo=link_repo, click_repo=click_repo
    )
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
