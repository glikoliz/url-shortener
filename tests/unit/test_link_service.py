from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_shorten_url_auto_code(link_service, mock_link):
    created_link = mock_link(short_code="AbC123")
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://google.com",
        user_id=1,
    )

    assert "short_url" in result
    link_service.link_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_shorten_url_auto_code_retry_on_collision(link_service, mock_link):
    created_link = mock_link(short_code="Free12")

    link_service.link_repo.get_by_code.side_effect = [mock_link(), None]
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://google.com",
        user_id=1,
    )

    assert link_service.link_repo.get_by_code.call_count == 2
    assert "Free12" in result["short_url"]


@pytest.mark.asyncio
async def test_shorten_url_custom_code(link_service, mock_link):
    created_link = mock_link(short_code="my-link")
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://example.com",
        user_id=1,
        custom_code="my-link",
    )

    assert "my-link" in result["short_url"]


@pytest.mark.asyncio
async def test_shorten_url_custom_code_taken(link_service, mock_link):
    link_service.link_repo.get_by_code.return_value = mock_link()

    with pytest.raises(HTTPException) as exc_info:
        await link_service.shorten_url(
            original_url="https://example.com",
            user_id=1,
            custom_code="abc123",
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_shorten_url_with_ttl(link_service, mock_link):
    created_link = mock_link(
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://example.com",
        user_id=1,
        ttl_minutes=30,
    )

    assert result["expires_at"] is not None
    link_service.link_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_link_success(link_service, mock_link):
    link = mock_link(original_url="https://google.com")
    link_service.link_repo.get_by_code.return_value = link

    url = await link_service.resolve_link("abc123")

    assert url == "https://google.com"
    link_service.link_repo.increment_clicks.assert_awaited_once_with(link.id)


@pytest.mark.asyncio
async def test_resolve_link_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.resolve_link("nonexistent")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_link_expired(link_service, mock_link):
    expired_link = mock_link(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    link_service.link_repo.get_by_code.return_value = expired_link

    with pytest.raises(HTTPException) as exc_info:
        await link_service.resolve_link("abc123")

    assert exc_info.value.status_code == 410


@pytest.mark.asyncio
async def test_get_stats_success(link_service, mock_link):
    link = mock_link(clicks=42, short_code="test01")
    link_service.link_repo.get_by_code.return_value = link

    result = await link_service.get_stats("test01")

    assert result["clicks"] == 42


@pytest.mark.asyncio
async def test_get_stats_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.get_stats("nonexistent")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_link_owner(link_service, mock_link):
    link = mock_link(user_id=1)
    link_service.link_repo.get_by_code.return_value = link

    await link_service.delete_link("abc123", user_id=1)

    link_service.link_repo.delete.assert_awaited_once_with(link)


@pytest.mark.asyncio
async def test_delete_link_non_owner(link_service, mock_link):
    link = mock_link(user_id=1)
    link_service.link_repo.get_by_code.return_value = link

    with pytest.raises(HTTPException) as exc_info:
        await link_service.delete_link("abc123", user_id=999)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_link_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.delete_link("nonexistent", user_id=1)

    assert exc_info.value.status_code == 404
