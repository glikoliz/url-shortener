import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserResponse

logger = logging.getLogger(__name__)

pwd_context = PasswordHash((BcryptHasher(),))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepository(db)

    async def register(self, email: str, password: str) -> UserResponse:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        password_hash = pwd_context.hash(password)
        user = await self.user_repo.create(email=email, password_hash=password_hash)
        logger.info(f"New user registered: {email}")
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.user_repo.get_by_email(email)
        if not user or not pwd_context.verify(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        access_token = self._create_access_token(user.id)
        refresh_token = await self._create_refresh_token(user.id)

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        result = await self.user_repo.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token, RefreshToken.revoked.is_(False)
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record or token_record.is_expired:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        # Rotate token: revoke old one and create new one
        token_record.revoked = True
        await self.user_repo.db.commit()

        access_token = self._create_access_token(token_record.user_id)
        new_refresh_token = await self._create_refresh_token(token_record.user_id)

        return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)

    @staticmethod
    def _create_access_token(user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_expiration_minutes
        )
        payload = {
            "sub": str(user_id),
            "exp": int(expire.timestamp()),
            "type": "access",
        }
        return jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    async def _create_refresh_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(64)
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expiration_days
        )

        new_token = RefreshToken(token=token, user_id=user_id, expires_at=expire)
        self.user_repo.db.add(new_token)
        await self.user_repo.db.commit()

        return token

    @staticmethod
    def verify_token(token: str) -> int:
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                )
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                )
            return int(user_id)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
