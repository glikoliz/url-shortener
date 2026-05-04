import string
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.link import Link
from app.services.link_service import _generate_short_code, _link_to_dict


def test_generate_short_code_default_length():
    code = _generate_short_code()
    assert len(code) == 6


def test_generate_short_code_custom_length():
    code = _generate_short_code(length=10)
    assert len(code) == 10


def test_generate_short_code_alphanumeric():
    allowed = set(string.ascii_letters + string.digits)
    for _ in range(50):
        code = _generate_short_code()
        assert all(c in allowed for c in code)


def test_generate_short_code_uniqueness():
    codes = {_generate_short_code() for _ in range(100)}
    assert len(codes) == 100


def test_link_to_dict_all_fields():
    link = MagicMock(spec=Link)
    link.id = 1
    link.original_url = "https://google.com"
    link.short_code = "abc123"
    link.clicks = 5
    link.created_at = datetime.now(timezone.utc)
    link.expires_at = None

    result = _link_to_dict(link)

    assert result == {
        "id": 1,
        "original_url": "https://google.com",
        "short_code": "abc123",
        "clicks": 5,
        "created_at": link.created_at.isoformat(),
        "expires_at": None,
    }


def test_link_to_dict_with_expiry():
    link = MagicMock(spec=Link)
    link.id = 2
    link.original_url = "https://example.com"
    link.short_code = "xyz789"
    link.clicks = 0
    link.created_at = datetime.now(timezone.utc)
    link.expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)

    result = _link_to_dict(link)

    assert result["expires_at"] == datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat()
