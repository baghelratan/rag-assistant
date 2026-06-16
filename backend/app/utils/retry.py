"""
Async retry decorator with exponential backoff and jitter.
"""

import asyncio
import functools
import logging
import random
from typing import Tuple, Type, Callable, Any

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Async retry decorator with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of attempts (including the first call).
        delay: Initial delay in seconds before the first retry.
        backoff: Multiplier applied to delay after each retry.
        jitter: Random fraction added to delay to avoid thundering herd.
        exceptions: Tuple of exception types to catch and retry on.

    Usage:
        @async_retry(max_attempts=3, delay=1.0, exceptions=(httpx.HTTPError,))
        async def call_api():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception = RuntimeError("Retry exhausted")

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        logger.error(
                            "Function '%s' failed after %d attempts: %s",
                            func.__name__, max_attempts, exc,
                        )
                        raise

                    wait = current_delay + random.uniform(0, jitter * current_delay)
                    logger.warning(
                        "Attempt %d/%d for '%s' failed: %s. Retrying in %.2fs…",
                        attempt, max_attempts, func.__name__, exc, wait,
                    )
                    await asyncio.sleep(wait)
                    current_delay *= backoff

            raise last_exception  # Should not reach here

        return wrapper

    return decorator
