from unittest.mock import MagicMock

import pytest
from fastapi import Request
from jose import jwt

from app.config import settings
from app.limiter import user_aware_identifier


@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.mark.asyncio
async def test_user_aware_identifier_authenticated(mock_request):
    token = jwt.encode(
        {"sub": "42"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    mock_request.cookies = {"access_token": token}

    identifier = await user_aware_identifier(mock_request)
    assert identifier == "user:42"


@pytest.mark.asyncio
async def test_user_aware_identifier_invalid_token_fallback_ip(mock_request):
    mock_request.cookies = {"access_token": "invalid-token"}
    mock_request.client.host = "192.168.1.1"

    identifier = await user_aware_identifier(mock_request)
    assert identifier == "192.168.1.1"


@pytest.mark.asyncio
async def test_user_aware_identifier_x_forwarded_for(mock_request):
    mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}

    identifier = await user_aware_identifier(mock_request)
    assert identifier == "10.0.0.1"


@pytest.mark.asyncio
async def test_user_aware_identifier_no_auth_no_proxy(mock_request):
    mock_request.client.host = "8.8.8.8"

    identifier = await user_aware_identifier(mock_request)
    assert identifier == "8.8.8.8"


@pytest.mark.asyncio
async def test_user_aware_identifier_unknown_client(mock_request):
    mock_request.client = None

    identifier = await user_aware_identifier(mock_request)
    assert identifier == "unknown"
