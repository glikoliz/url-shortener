from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click_event import ClickEvent
from app.repositories.click_repository import ClickRepository


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session):
    return ClickRepository(mock_session)


@pytest.mark.asyncio
async def test_create_click(repo, mock_session):
    click = ClickEvent(link_id=1, ip_address="1.2.3.4")
    result = await repo.create(click)

    mock_session.add.assert_called_once_with(click)
    assert result == click


@pytest.mark.asyncio
async def test_get_by_link_id_with_filters(repo, mock_session):
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 10

    mock_items_result = MagicMock()
    mock_items_result.scalars().all.return_value = [ClickEvent(id=1)]

    mock_session.execute.side_effect = [mock_count_result, mock_items_result]

    items, total = await repo.get_by_link_id(1, ip="1.2.3", country="US")

    assert total == 10
    assert len(items) == 1
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_get_by_link_id_country_null(repo, mock_session):
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 5
    mock_items_result = MagicMock()
    mock_items_result.scalars().all.return_value = []

    mock_session.execute.side_effect = [mock_count_result, mock_items_result]

    await repo.get_by_link_id(1, country="null")

    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_get_aggregated_stats_granularity_auto_minute(repo, mock_session):
    now = datetime.now(timezone.utc)
    mock_range = MagicMock()
    mock_range.one.return_value = MagicMock(min_t=now, max_t=now + timedelta(minutes=5))

    mock_summary = MagicMock()
    mock_summary.one.return_value = MagicMock(total=10, unique=5, unique_ips=3)

    mock_empty = MagicMock()
    mock_empty.all.return_value = []

    mock_session.execute.side_effect = [
        mock_range,  # range_query
        mock_summary,  # summary_query
        mock_empty,  # clicks_query
        mock_empty,  # referers_query
        mock_empty,  # countries_query
    ]

    stats = await repo.get_aggregated_stats(1)
    assert stats["granularity"] == "minute"
    assert stats["total_clicks"] == 10


@pytest.mark.asyncio
async def test_get_aggregated_stats_granularity_auto_hour(repo, mock_session):
    now = datetime.now(timezone.utc)
    mock_range = MagicMock()
    mock_range.one.return_value = MagicMock(min_t=now, max_t=now + timedelta(hours=10))

    mock_summary = MagicMock()
    mock_summary.one.return_value = MagicMock(total=0, unique=0, unique_ips=0)

    mock_session.execute.side_effect = [
        mock_range,
        mock_summary,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    stats = await repo.get_aggregated_stats(1)
    assert stats["granularity"] == "hour"


@pytest.mark.asyncio
async def test_get_aggregated_stats_provided_granularity(repo, mock_session):
    mock_summary = MagicMock()
    mock_summary.one.return_value = MagicMock(total=0, unique=0, unique_ips=0)

    mock_session.execute.side_effect = [
        mock_summary,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    stats = await repo.get_aggregated_stats(1, granularity="day")
    assert stats["granularity"] == "day"
    assert mock_session.execute.call_count == 4
