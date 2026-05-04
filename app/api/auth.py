from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import get_auth_service, get_current_user
from app.config import settings
from app.limiter import RateLimiter
from app.models.user import User
from app.schemas.user import MessageResponse, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.jwt_expiration_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.refresh_token_expiration_days * 24 * 60 * 60,
    )


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
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    result = await service.refresh_token(refresh_token)
    set_auth_cookies(response, result.access_token, result.refresh_token)
    return MessageResponse(message="Token refreshed")


@router.get("/logout", response_model=MessageResponse)
@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
