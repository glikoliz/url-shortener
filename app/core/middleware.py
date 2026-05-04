import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # Access-log style: GET /path -> 200 (5.23ms)
        logger.info(
            f"{request.method:<5} {request.url.path} -> "
            f"{response.status_code} ({process_time:.2f}ms)"
        )

        return response
