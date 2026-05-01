from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.redis import get_redis
from app.schemas.link import LinkCreate, LinkResponse
from app.services.link_service import LinkService

router = APIRouter()
redirect_router = APIRouter()


@router.post("", response_model=LinkResponse, status_code=201)
async def create_short_link(
    body: LinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    service = LinkService(db, redis)
    result = await service.shorten_url(
        original_url=str(body.original_url),
        user_id=current_user.id,
        custom_code=body.custom_code,
        ttl_minutes=body.ttl_minutes,
    )
    return result


@router.get("/{short_code}", response_model=LinkResponse)
async def get_link_info(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    service = LinkService(db)
    return await service.get_stats(short_code)


@router.delete("/{short_code}", status_code=204)
async def delete_link(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    service = LinkService(db, redis)
    await service.delete_link(short_code, user_id=current_user.id)


@redirect_router.get("/s/{short_code}")
async def redirect_to_original(
    short_code: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = LinkService(db, redis)
    original_url = await service.resolve_link(short_code)
    background_tasks.add_task(service.count_click, short_code)
    return RedirectResponse(url=original_url, status_code=302)

