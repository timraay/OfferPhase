import asyncio
import logging
from typing import Coroutine
from cachetools import TTLCache
from cachetools.keys import hashkey
from functools import wraps

def async_ttl_cache(size: int, seconds: int):
    def decorator(func):
        func.cache = TTLCache(size, ttl=seconds)
        @wraps(func)
        async def wrapper(*args, **kwargs):
            k = hashkey(*args, **kwargs)
            try:
                return func.cache[k]
            except KeyError:
                pass  # key not found
            v = await func(*args, **kwargs)
            try:
                func.cache[k] = v
            except ValueError:
                pass  # value too large
            return v
        return wrapper
    return decorator

class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

def safe_create_task(
        coro: Coroutine,
        err_msg: str | None = None,
        name: str | None = None,
        logger: logging.Logger = logging # type: ignore
):
    def _task_inner(t: asyncio.Task):
        if t.cancelled():
            logger.warning(f"Task {task.get_name()} was cancelled")
        elif exc := t.exception():
            logger.error(
                err_msg or f"Unexpected error during task {task.get_name()}",
                exc_info=exc
            )
    task = asyncio.create_task(coro, name=name)
    task.add_done_callback(_task_inner)
    return task
