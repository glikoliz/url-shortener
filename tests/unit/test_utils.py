import string

from app.services.link_service import _generate_short_code


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
