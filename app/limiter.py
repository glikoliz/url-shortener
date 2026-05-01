from typing import Callable, Dict, Optional

from fastapi import Request, Response
from fastapi_limiter.depends import RateLimiter as BaseRateLimiter
from fastapi_limiter.depends import default_callback, default_identifier
from pyrate_limiter import Duration, Limiter, Rate, RedisBucket
from redis.asyncio import Redis


class LimiterManager:
    def __init__(self) -> None:
        self.limiters: Dict[str, Limiter] = {}

    async def init_limiter(
        self, name: str, redis: Redis, requests: int, seconds: int
    ) -> Limiter:
        if name not in self.limiters:
            rate = Rate(requests, seconds * Duration.SECOND)
            bucket = await RedisBucket.init(
                rates=[rate], redis=redis, bucket_key=f"limiter:{name}"
            )
            self.limiters[name] = Limiter(bucket)
        return self.limiters[name]

    def get_limiter(self, name: str) -> Optional[Limiter]:
        return self.limiters.get(name)


limiter_manager = LimiterManager()


class RateLimiter(BaseRateLimiter):
    """
    Lazy RateLimiter that resolves the limiter object at call time.
    This avoids issues with initialization order in FastAPI.
    """

    def __init__(
        self,
        name: str,
        identifier: Callable = default_identifier,
        callback: Callable = default_callback,
        blocking: bool = False,
    ):
        self.name = name
        self.identifier = identifier
        self.callback = callback
        self.blocking = blocking

    async def __call__(self, request: Request, response: Response):
        limiter = limiter_manager.get_limiter(self.name)
        if not limiter:
            return

        self.limiter = limiter
        return await super().__call__(request, response)
