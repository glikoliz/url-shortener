import logging
import time

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

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


class ContentLengthLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length:
                if int(content_length) > settings.max_request_size:
                    return Response(
                        content="Request body too large",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
        return await call_next(request)
