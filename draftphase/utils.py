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
