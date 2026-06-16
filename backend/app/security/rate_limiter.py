"""
Rate limiter setup using slowapi.
"""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)

# Global limiter instance — imported by main.py
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT],
    headers_enabled=True,  # includes RateLimit-* headers in responses
)


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    Returns JSON 429 response instead of plain text.
    """
    logger.warning(
        "Rate limit exceeded: ip=%s path=%s",
        get_remote_address(request),
        request.url.path,
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please wait before retrying.",
            "retry_after": "60",
        },
        headers={"Retry-After": "60"},
    )
