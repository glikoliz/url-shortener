import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.dependencies import (
    get_current_user,
    get_link_service,
    get_optional_current_user,
)
from app.core.responses import SSEResponse
from app.core.utils import get_client_country, get_client_ip
from app.limiter import RateLimiter
from app.models.user import User
from app.schemas.click import ClickStatsResponse, PaginatedClickResponse
from app.schemas.link import LinkCreate, LinkResponse
from app.services.link_service import LinkService

router = APIRouter()
redirect_router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=LinkResponse,
    status_code=201,
    dependencies=[Depends(RateLimiter(name="links:create"))],
)
async def create_link(
    link_data: LinkCreate,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.shorten_url(
        original_url=str(link_data.original_url),
        user_id=current_user.id if current_user else None,
        custom_code=link_data.custom_code,
        ttl_minutes=link_data.ttl_minutes,
        background_tasks=background_tasks,
    )


@router.get("", response_model=list[LinkResponse])
async def get_my_links(
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_user_links(current_user.id)


@router.get("/events/stream")
async def stream_updates(
    current_user: User = Depends(get_current_user),
    service: LinkService = Depends(get_link_service),
):
    return SSEResponse(service.get_updates_stream(current_user.id))


@router.get("/i/{short_code}/info", response_model=LinkResponse)
async def get_link_info(
    short_code: str,
    current_user: User | None = Depends(get_optional_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_link_info(
        short_code, current_user.id if current_user else None
    )


@router.get("/i/{short_code}/stats", response_model=ClickStatsResponse)
async def get_link_stats(
    short_code: str,
    granularity: str | None = None,
    current_user: User | None = Depends(get_optional_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_click_stats(
        short_code, current_user.id if current_user else None, granularity=granularity
    )


@router.get("/i/{short_code}/clicks", response_model=PaginatedClickResponse)
async def get_link_clicks(
    short_code: str,
    skip: int = 0,
    limit: int = 50,
    ip: str | None = None,
    country: str | None = None,
    sort_by: str = "clicked_at",
    sort_dir: str = "desc",
    current_user: User | None = Depends(get_optional_current_user),
    service: LinkService = Depends(get_link_service),
):
    return await service.get_clicks(
        short_code,
        current_user.id if current_user else None,
        skip=skip,
        limit=limit,
        ip=ip,
        country=country,
        sort_by=sort_by,
        sort_dir=sort_dir,
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
    target_url = await service.handle_click(
        short_code=short_code,
        ip=get_client_ip(request),
        country=get_client_country(request),
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        background_tasks=background_tasks,
    )

    if target_url:
        return RedirectResponse(url=target_url, status_code=302)

    return Response(content="Link preview disabled", status_code=403)
