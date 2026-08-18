import asyncio
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())
                    logger.warning(f"{func.__name__} attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


async def retry_with_backoff_async(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= (0.5 + random.random())
                    logger.warning(f"{func.__name__} attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def count_words(text: str) -> int:
    return len(text.split())


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)].rstrip() + suffix


def sanitize_filename(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).rstrip()


def extract_code_blocks(text: str) -> list:
    import re
    pattern = r"```(\w+)?\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)


def format_as_markdown(content: str) -> str:
    lines = content.split("\n")
    formatted = []
    in_code_block = False
    code_language = ""

    for line in lines:
        if line.startswith("```"):
            if not in_code_block:
                code_language = line[3:].strip()
                formatted.append(f"```{code_language}")
                in_code_block = True
            else:
                formatted.append("```")
                in_code_block = False
        else:
            formatted.append(line)

    return "\n".join(formatted)