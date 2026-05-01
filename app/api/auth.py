from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.limiter import RateLimiter
from app.schemas.user import TokenResponse, UserRegister, UserRegisterResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=201,
    dependencies=[Depends(RateLimiter(name="auth:register"))],
)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.register(email=body.email, password=body.password)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimiter(name="auth:login"))],
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    token = await service.login(email=form.username, password=form.password)
    return TokenResponse(access_token=token)
