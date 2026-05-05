import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import select

from app.config import settings
from app.core.uow import AbstractUnitOfWork
from app.models.refresh_token import RefreshToken
from app.schemas.user import TokenResponse, UserResponse

logger = logging.getLogger(__name__)

pwd_context = PasswordHash((BcryptHasher(),))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthService:
    def __init__(self, uow: AbstractUnitOfWork) -> None:
        self.uow = uow

    async def register(self, email: str, password: str) -> UserResponse:
        async with self.uow:
            existing = await self.uow.users.get_by_email(email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
            password_hash = pwd_context.hash(password)
            user = await self.uow.users.create(email=email, password_hash=password_hash)
            await self.uow.commit()
            await self.uow.session.refresh(user)
            logger.info(f"New user registered: {email}")
            return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        async with self.uow:
            user = await self.uow.users.get_by_email(email)
            if not user or not pwd_context.verify(password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

            access_token = self._create_access_token(user.id)
            refresh_token = await self._create_refresh_token(user.id)

            return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(self, refresh_token: str | None) -> TokenResponse:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        async with self.uow:
            result = await self.uow.session.execute(
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
            await self.uow.commit()

            access_token = self._create_access_token(token_record.user_id)
            new_refresh_token = await self._create_refresh_token(token_record.user_id)

            return TokenResponse(
                access_token=access_token, refresh_token=new_refresh_token
            )

    @staticmethod
    def _create_access_token(user_id: int) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.jwt_expiration_minutes)
        payload = {
            "sub": str(user_id),
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "jti": secrets.token_hex(8),
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
        self.uow.session.add(new_token)
        await self.uow.commit()

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
