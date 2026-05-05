from unittest.mock import MagicMock, patch

import pytest

from app.services.link_service import _generate_short_code, _resolve_final_url


@pytest.mark.asyncio
async def test_resolve_final_url_helper():
    mock_resp = MagicMock()
    mock_resp.url = "https://example.com/final"

    with patch("httpx.AsyncClient.head", return_value=mock_resp):
        url = await _resolve_final_url("example.com")
        assert url == "https://example.com/final"

    with patch("httpx.AsyncClient.head", side_effect=Exception("Timeout")):
        url = await _resolve_final_url("example.com")
        assert url == "https://example.com"

    with patch("httpx.AsyncClient.head", side_effect=Exception("Timeout")):
        url = await _resolve_final_url("http://test.com")
        assert url == "http://test.com"


def test_generate_short_code():
    code = _generate_short_code(8)
    assert len(code) == 8
    assert isinstance(code, str)
