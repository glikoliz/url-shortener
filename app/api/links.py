import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app import database
from app.api.dependencies import (
    get_current_user,
    get_link_service,
    get_user_id_from_token,
)
from app.limiter import RateLimiter, user_aware_identifier
from app.models.user import User
from app.redis import redis_client
from app.schemas.click import ClickStatsResponse, PaginatedClickResponse
from app.schemas.link import LinkCreate, LinkResponse
from app.services.link_service import LinkService

router = APIRouter()
redirect_router = APIRouter()


async def _background_record_click(
    short_code: str, ip: str | None, user_agent: str | None, referer: str | None
):
    try:
        async with database.db_session() as db:
            service = LinkService(db, redis=redis_client)
            await service.count_click(short_code, ip, user_agent, referer)
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Background task failed for {short_code}: {e}", exc_info=True
        )


@router.post(
    "",
    response_model=LinkResponse,
    status_code=201,
    dependencies=[
        Depends(RateLimiter(name="links:create", identifier=user_aware_identifier))
    ],
)
async def create_short_link(
    body: LinkCreate,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    result = await service.shorten_url(
        original_url=str(body.original_url),
        user_id=current_user.id,
        custom_code=body.custom_code,
        ttl_minutes=body.ttl_minutes,
    )
    return result


@router.get("", response_model=list[LinkResponse])
async def get_my_links(
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_user_links(current_user.id)


@router.get("/events/stream")
async def stream_link_updates(
    user_id: int = Depends(get_user_id_from_token),
    service: LinkService = Depends(get_link_service),
):
    return StreamingResponse(
        service.get_updates_stream(user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/i/{short_code}/info", response_model=LinkResponse)
async def get_link_info(
    short_code: str,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_stats(short_code, current_user.id)


@router.get("/i/{short_code}/clicks", response_model=PaginatedClickResponse)
async def get_link_clicks(
    short_code: str,
    skip: int = 0,
    limit: int = 50,
    ip: str | None = None,
    country: str | None = None,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_clicks(
        short_code,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        ip=ip,
        country=country,
    )


@router.get("/i/{short_code}/stats", response_model=ClickStatsResponse)
async def get_link_stats(
    short_code: str,
    granularity: str | None = None,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_click_stats(
        short_code, current_user.id, granularity=granularity
    )


@router.delete("/i/{short_code}", status_code=204)
async def delete_link(
    short_code: str,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    await service.delete_link(short_code, user_id=current_user.id)


@redirect_router.get(
    "/s/{short_code}", dependencies=[Depends(RateLimiter(name="links:redirect"))]
)
async def redirect_to_original(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    service: LinkService = Depends(get_link_service),
):
    original_url = await service.resolve_link(short_code)

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("referer")

    await service.increment_click_redis(short_code)

    background_tasks.add_task(
        _background_record_click,
        short_code,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
    )

    return RedirectResponse(url=original_url, status_code=302)
