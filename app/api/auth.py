from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.limiter import RateLimiter
from app.schemas.user import TokenResponse, UserRegister, UserRegisterResponse
from app.services.auth_service import AuthService, get_auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=UserRegisterResponse,
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
    response_model=TokenResponse,
    dependencies=[Depends(RateLimiter(name="auth:login"))],
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    result = await service.login(email=form.username, password=form.password)
    return result
