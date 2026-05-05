from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import TokenResponse
from app.services.auth_service import AuthService, pwd_context


@pytest.mark.asyncio
async def test_register_success(auth_service, mock_user):
    auth_service.user_repo.get_by_email.return_value = None
    created_user = mock_user(id=1, email="new@example.com")
    auth_service.user_repo.create.return_value = created_user

    result = await auth_service.register("new@example.com", "secret123")

    auth_service.user_repo.get_by_email.assert_awaited_once_with("new@example.com")
    auth_service.user_repo.create.assert_awaited_once()
    assert result.email == "new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(auth_service, mock_user):
    auth_service.user_repo.get_by_email.return_value = mock_user()

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register("test@example.com", "secret123")

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_success(auth_service, mock_user):
    password = "correct_password"
    hashed = pwd_context.hash(password)
    user = mock_user(id=42, password_hash=hashed)
    auth_service.user_repo.get_by_email.return_value = user

    token_response = await auth_service.login("test@example.com", password)

    assert isinstance(token_response, TokenResponse)
    assert isinstance(token_response.access_token, str)


@pytest.mark.asyncio
async def test_login_wrong_email(auth_service):
    auth_service.user_repo.get_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("nonexistent@example.com", "password")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(auth_service, mock_user):
    hashed = pwd_context.hash("correct_password")
    user = mock_user(password_hash=hashed)
    auth_service.user_repo.get_by_email.return_value = user

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("test@example.com", "wrong_password")

    assert exc_info.value.status_code == 401


def test_verify_token_valid():
    token = AuthService._create_access_token(user_id=7)
    result = AuthService.verify_token(token)
    assert result == 7


def test_verify_token_expired():
    with patch("app.services.auth_service.settings") as mock_settings:
        mock_settings.jwt_secret = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expiration_minutes = -60
        token = AuthService._create_access_token(user_id=1)

    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_token(token)

    assert exc_info.value.status_code == 401


def test_verify_token_garbage():
    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_token("not.a.valid.token")

    assert exc_info.value.status_code == 401


def test_verify_token_missing_sub():
    from jose import jwt

    from app.config import settings

    payload = {"exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(HTTPException) as exc_info:
        AuthService.verify_token(token)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_success(mock_uow):
    user = User(id=1, is_active=True)

    with patch("app.api.dependencies.AuthService.verify_token", return_value=1):
        mock_uow.users.get_by_id.return_value = user
        result = await get_current_user(access_token="valid_token", uow=mock_uow)

        assert result == user
        mock_uow.users.get_by_id.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_current_user_not_found(mock_uow):
    with patch("app.api.dependencies.AuthService.verify_token", return_value=999):
        mock_uow.users.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token="valid_token", uow=mock_uow)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_get_current_user_deactivated(mock_uow):
    deactivated_user = User(id=1, is_active=False)

    with patch("app.api.dependencies.AuthService.verify_token", return_value=1):
        mock_uow.users.get_by_id.return_value = deactivated_user
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token="valid_token", uow=mock_uow)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "User account is deactivated"


@pytest.mark.asyncio
async def test_refresh_token_success(auth_service, mock_uow):
    # Mock the refresh token record
    mock_token = MagicMock()
    mock_token.token = "valid_refresh"
    mock_token.user_id = 1
    mock_token.revoked = False
    mock_token.is_expired = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_token
    auth_service.uow.session.execute.return_value = mock_result

    response = await auth_service.refresh_token("valid_refresh")

    assert response.access_token is not None
    assert response.refresh_token is not None
    assert mock_token.revoked is True
    auth_service.uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_refresh_token_invalid(auth_service, mock_uow):
    # Mock no token found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    auth_service.uow.session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.refresh_token("invalid_refresh")

    assert exc_info.value.status_code == 401
    assert "Invalid or expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_token_none(auth_service):
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.refresh_token(None)

    assert exc_info.value.status_code == 401
    assert "Refresh token missing" in exc_info.value.detail
