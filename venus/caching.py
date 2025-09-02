"""
Caching utilities for both coroutine and synchronous functions.
"""

import functools
import inspect
import typing

from ._decorator_utils import makekey
from .types import CacheManagerType, CacheTypes, CallableType, ReturnType

try:
    import aiocache
    import async_lru
    import cachetools
except ImportError as e:
    raise ImportError(
        'Can not import cache modules! Install using `uv add "venai[cache]"`'
    ) from e


class CachedFuncContext(typing.Generic[CallableType, CacheManagerType]):
    cache: type[CacheManagerType]
    """
    Cache manager type for the cached function.
    """


def cached(
    fn: typing.Callable | None = None,
    /,
    *,
    key: str | typing.Callable[[], str] | None = None,
    ttl: int = 60,
    maxsize: int = 128,
    typed: bool = False,
    cache_type: CacheTypes = "ttl",
    **options: typing.Any,
):
    """
    Decorator to cache the results of a function.
    This decorator uses `aiocache` for coroutine functions and `cachetools` for synchronous functions.

    If the function is a coroutine, it uses `aiocache.cached` with a TTL
    of 60 seconds.

    If the function is synchronous, it uses `cachetools.cached`
    with various cache types based on the 'type' parameter.
    """

    if cache_type == "python-lru":
        return functools.lru_cache(maxsize=maxsize, typed=typed)

    def decorator(
        func: CallableType,
    ) -> CachedFuncContext[
        typing.Callable[..., ReturnType], typing.Union[aiocache.Cache, cachetools.Cache]
    ]:
        if inspect.iscoroutinefunction(func):
            if cache_type == "async-lru":
                cache = async_lru.alru_cache(maxsize=maxsize, typed=typed, ttl=ttl)(
                    func
                )
                cache.clear = cache.cache_clear
                cache.cache = cache
                return cache

            cachekey = key() if callable(key) else key
            try:
                from aiocache import cached as acached

                return acached(ttl=ttl, key=cachekey or makekey(fn), **options)(func)
            except ImportError as e:
                raise ImportError(
                    "The 'aiocache' package is required for coroutine functions. "
                    "Please install it using 'pip install aiocache'."
                ) from e
        else:
            try:
                from cachetools import (FIFOCache, LFUCache, LRUCache, RRCache,
                                        TLRUCache, TTLCache, cached)
                from cachetools.keys import hashkey

                cachekey = (
                    key
                    if callable(key)
                    else (lambda *args, **kwargs: key) if key else hashkey
                )

                cache_types = {
                    "fifo": FIFOCache(maxsize=maxsize),
                    "lfu": LFUCache(maxsize=maxsize),
                    "lru": LRUCache(maxsize=maxsize),
                    "rr": RRCache(maxsize=maxsize),
                    "tlru": TLRUCache(maxsize=maxsize, ttu=lambda _, __, ___: ttl),
                    "ttl": TTLCache(maxsize=maxsize, ttl=ttl),
                }

                assert (
                    cache_type in cache_types
                ), f"Invalid cache type: {cache_type}. Valid types are python-lru, async-lru, {', '.join(list(cache_types.keys()))}."

                func.cache = cache_types[cache_type]
                return cached(func.cache, key=cachekey, **options)(func)  # type: ignore
            except ImportError as e:
                raise ImportError(
                    "The 'cachetools' package is required for synchronous functions. "
                    "Please install it using 'pip install cachetools'."
                ) from e

    return decorator if fn is None else decorator(fn)
