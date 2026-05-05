from typing import AsyncGenerator

from fastapi import Cookie, Depends, Query

from app.core.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork
from app.models.user import User
from app.redis import get_redis
from app.services.auth_service import AuthService
from app.services.link_service import LinkService


async def get_uow() -> AsyncGenerator[AbstractUnitOfWork, None]:
    uow = SqlAlchemyUnitOfWork()
    async with uow:
        yield uow


def get_auth_service(uow: AbstractUnitOfWork = Depends(get_uow)) -> AuthService:
    return AuthService(uow)


async def get_current_user(
    access_token: str | None = Cookie(None),
    service: AuthService = Depends(get_auth_service),
) -> User:
    return await service.get_authenticated_user(access_token)


def get_link_service(
    uow: AbstractUnitOfWork = Depends(get_uow), redis=Depends(get_redis)
) -> LinkService:
    return LinkService(uow, redis=redis)


def get_user_id_from_token(
    access_token: str | None = Cookie(None),
    token: str | None = Query(None),
) -> int:
    return AuthService.verify_token(access_token or token)
