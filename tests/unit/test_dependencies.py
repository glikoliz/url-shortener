from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_uow, get_user_id_from_token
from app.core.uow import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_get_uow_yields_uow():
    mock_uow_instance = MagicMock(spec=SqlAlchemyUnitOfWork)
    mock_uow_instance.__aenter__ = AsyncMock(return_value=mock_uow_instance)
    mock_uow_instance.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.api.dependencies.SqlAlchemyUnitOfWork", return_value=mock_uow_instance
    ):
        generator = get_uow()
        uow = await generator.__anext__()
        assert uow == mock_uow_instance

        try:
            await generator.__anext__()
        except StopAsyncIteration:
            pass

        mock_uow_instance.__aenter__.assert_awaited_once()
        mock_uow_instance.__aexit__.assert_awaited_once()


def test_get_user_id_from_token_cookie_success():
    with patch("app.api.dependencies.AuthService.verify_token", return_value=123):
        result = get_user_id_from_token(access_token="cookie_token", token=None)
        assert result == 123


def test_get_user_id_from_token_query_success():
    with patch("app.api.dependencies.AuthService.verify_token", return_value=456):
        result = get_user_id_from_token(access_token=None, token="query_token")
        assert result == 456


def test_get_user_id_from_token_missing():
    with pytest.raises(HTTPException) as exc_info:
        get_user_id_from_token(access_token=None, token=None)

    assert exc_info.value.status_code == 401
    assert "token missing" in exc_info.value.detail.lower()


def test_get_user_id_from_token_invalid():
    with patch("app.api.dependencies.AuthService.verify_token") as mock_verify:
        mock_verify.side_effect = HTTPException(status_code=401, detail="Invalid token")

        with pytest.raises(HTTPException) as exc_info:
            get_user_id_from_token(access_token="bad_token")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"
