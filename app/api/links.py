from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_current_user, get_link_service
from app.limiter import RateLimiter
from app.models.user import User
from app.schemas.click import (
    ClickStatsResponse,
    PaginatedClickResponse,
)
from app.schemas.link import LinkCreate, LinkResponse
from app.services.link_service import LinkService

router = APIRouter()
redirect_router = APIRouter()


@router.post(
    "",
    response_model=LinkResponse,
    status_code=201,
    dependencies=[Depends(RateLimiter(name="links:create"))],
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
async def get_user_links(
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_user_links(current_user.id)


@router.get("/{short_code}", response_model=LinkResponse)
async def get_link_info(
    short_code: str,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_stats(short_code, current_user.id)


@router.get("/{short_code}/clicks", response_model=PaginatedClickResponse)
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
        short_code, current_user.id, skip=skip, limit=limit, ip=ip, country=country
    )


@router.get("/{short_code}/stats", response_model=ClickStatsResponse)
async def get_link_stats(
    short_code: str,
    granularity: str | None = None,
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_click_stats(
        short_code, current_user.id, granularity=granularity
    )


@router.delete("/{short_code}", status_code=204)
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

    background_tasks.add_task(
        service.count_click, short_code, ip=ip, user_agent=user_agent, referer=referer
    )
    return RedirectResponse(url=original_url, status_code=302)
