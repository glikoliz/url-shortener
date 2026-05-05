from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import Link
from app.models.user import User
from app.repositories.link_repository import LinkRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_link_repo_create(mock_session):
    repo = LinkRepository(mock_session)
    link = Link(short_code="abc")
    await repo.create(link)
    mock_session.add.assert_called_once_with(link)


@pytest.mark.asyncio
async def test_link_repo_get_by_code(mock_session):
    repo = LinkRepository(mock_session)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = Link(short_code="abc")
    mock_session.execute.return_value = mock_result

    link = await repo.get_by_code("abc")
    assert link.short_code == "abc"


@pytest.mark.asyncio
async def test_link_repo_increment_clicks(mock_session):
    repo = LinkRepository(mock_session)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    mock_session.execute.return_value = mock_result

    clicks = await repo.increment_clicks(1)
    assert clicks == 42


@pytest.mark.asyncio
async def test_user_repo_create(mock_session):
    repo = UserRepository(mock_session)
    user = await repo.create("test@ex.com", "hash")
    assert user.email == "test@ex.com"
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_user_repo_get_by_id(mock_session):
    repo = UserRepository(mock_session)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = User(id=1, email="test@ex.com")
    mock_session.execute.return_value = mock_result

    user = await repo.get_by_id(1)
    assert user.id == 1
