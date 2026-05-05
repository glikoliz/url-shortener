from typing import Any

from fastapi.responses import StreamingResponse


class SSEResponse(StreamingResponse):
    """
    Custom response class for Server-Sent Events (SSE).
    Automatically sets required headers and media type.
    """

    def __init__(self, content: Any, **kwargs):
        headers = kwargs.get("headers", {})
        headers.update(
            {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
        kwargs["headers"] = headers
        super().__init__(content, media_type="text/event-stream", **kwargs)
