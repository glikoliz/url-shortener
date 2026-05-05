from typing import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException, Query, status

from app.core.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork
from app.models.user import User
from app.redis import get_redis
from app.services.auth_service import AuthService
from app.services.link_service import LinkService


async def get_uow() -> AsyncGenerator[AbstractUnitOfWork, None]:
    uow = SqlAlchemyUnitOfWork()
    async with uow:
        yield uow


async def get_current_user(
    access_token: str | None = Cookie(None),
    uow: AbstractUnitOfWork = Depends(get_uow),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        user_id = AuthService.verify_token(access_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def get_auth_service(uow: AbstractUnitOfWork = Depends(get_uow)) -> AuthService:
    return AuthService(uow)


def get_link_service(
    uow: AbstractUnitOfWork = Depends(get_uow), redis=Depends(get_redis)
) -> LinkService:
    return LinkService(uow, redis=redis)


def get_user_id_from_token(
    access_token: str | None = Cookie(None),
    token: str | None = Query(None),
) -> int:
    token_to_verify = access_token or token
    if not token_to_verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing",
        )
    return AuthService.verify_token(token_to_verify)
