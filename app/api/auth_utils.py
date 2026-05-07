from fastapi import Response

from app.config import settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none",
        max_age=int(settings.jwt_expiration_minutes) * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none",
        max_age=int(settings.refresh_token_expiration_days) * 24 * 60 * 60,
    )


def delete_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none",
    )
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none",
    )
