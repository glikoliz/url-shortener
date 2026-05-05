import abc
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.click_repository import ClickRepository
from app.repositories.link_repository import LinkRepository
from app.repositories.user_repository import UserRepository


class AbstractUnitOfWork(abc.ABC):
    users: UserRepository
    links: LinkRepository
    clicks: ClickRepository
    session: AsyncSession

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.rollback()

    @abc.abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self):
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        if session_factory is None:
            from app.database import AsyncSessionLocal

            session_factory = AsyncSessionLocal
        self.session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._nesting_level = 0

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use 'async with uow:'")
        return self._session

    async def __aenter__(self):
        self._nesting_level += 1
        if self._session is None:
            self._session = self.session_factory()
            self.users = UserRepository(self._session)
            self.links = LinkRepository(self._session)
            self.clicks = ClickRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._nesting_level -= 1

        if exc_type:
            await self.rollback()

        if self._nesting_level == 0:
            if self._session:
                await self._session.close()
                self._session = None

    async def commit(self):
        if self._session:
            await self._session.commit()

    async def rollback(self):
        if self._session:
            await self._session.rollback()
