from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api.auth_utils import delete_auth_cookies, set_auth_cookies
from app.api.dependencies import get_auth_service, get_current_user
from app.limiter import RateLimiter
from app.models.user import User
from app.schemas.user import MessageResponse, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(RateLimiter(name="auth:register"))],
)
async def register(
    body: UserRegister, service: AuthService = Depends(get_auth_service)
):
    user = await service.register(email=body.email, password=body.password)
    return user


@router.post(
    "/login",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter(name="auth:login"))],
)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    result = await service.login(email=form.username, password=form.password)
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return MessageResponse(message="Logged in successfully")


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(None),
    service: AuthService = Depends(get_auth_service),
):
    result = await service.refresh_token(refresh_token)
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return MessageResponse(message="Token refreshed")


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    delete_auth_cookies(response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
