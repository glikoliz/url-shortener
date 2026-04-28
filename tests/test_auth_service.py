from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

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

    token = await auth_service.login("test@example.com", password)

    assert isinstance(token, str)


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
    token = AuthService._create_token(user_id=7)
    result = AuthService.verify_token(token)
    assert result == 7


def test_verify_token_expired():
    with patch("app.services.auth_service.settings") as mock_settings:
        mock_settings.jwt_secret = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expiration_minutes = -60
        token = AuthService._create_token(user_id=1)

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
