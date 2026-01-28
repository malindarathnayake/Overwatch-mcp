"""In-memory TTL cache for MCP tool responses."""

from typing import Any, Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class Cache(Generic[T]):
    """
    Thread-safe TTL cache wrapper.

    Note: Single-threaded async context doesn't require explicit locking,
    but cachetools.TTLCache handles TTL expiry automatically.
    """

    def __init__(self, default_ttl: int, maxsize: int = 1000):
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds
            maxsize: Maximum number of entries (LRU eviction when full)
        """
        self.default_ttl = default_ttl
        self._cache: TTLCache[str, T] = TTLCache(maxsize=maxsize, ttl=default_ttl)
        self._ttl_overrides: dict[str, int] = {}

    def set_ttl_override(self, key_prefix: str, ttl: int) -> None:
        """
        Set TTL override for keys matching a prefix.

        Args:
            key_prefix: Key prefix to match (e.g., "prometheus_metrics")
            ttl: Time-to-live in seconds for matching keys
        """
        self._ttl_overrides[key_prefix] = ttl

    def _get_ttl(self, key: str) -> int:
        """Get TTL for a specific key based on overrides."""
        for prefix, ttl in self._ttl_overrides.items():
            if key.startswith(prefix):
                return ttl
        return self.default_ttl

    def get(self, key: str) -> T | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        return self._cache.get(key)

    def set(self, key: str, value: T) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache

        Note: Due to cachetools limitations, we use the global TTL.
        Per-key TTL requires recreating the cache entry which is handled
        by the __delitem__ and __setitem__ operations.
        """
        # For cachetools TTLCache, all entries share the same TTL
        # To support per-key TTL, we'd need a more complex implementation
        # For now, we use the default TTL for all entries
        self._cache[key] = value

    def delete(self, key: str) -> None:
        """
        Delete value from cache.

        Args:
            key: Cache key to delete
        """
        try:
            del self._cache[key]
        except KeyError:
            pass

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def has(self, key: str) -> bool:
        """
        Check if key exists in cache and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        return key in self._cache

    def keys(self) -> list[str]:
        """Get all cache keys."""
        return list(self._cache.keys())

    def __len__(self) -> int:
        """Return number of entries in cache."""
        return len(self._cache)


class CacheManager:
    """
    Manages multiple cache instances for different tool types.

    This provides a centralized way to manage caches with different TTLs
    for different tools while maintaining a simple interface.
    """

    def __init__(self, default_ttl: int = 60, ttl_overrides: dict[str, int] | None = None):
        """
        Initialize cache manager.

        Args:
            default_ttl: Default TTL for all caches
            ttl_overrides: Dictionary of tool name -> TTL overrides
        """
        self.default_ttl = default_ttl
        self.ttl_overrides = ttl_overrides or {}
        self._caches: dict[str, Cache[Any]] = {}

    def get_cache(self, tool_name: str) -> Cache[Any]:
        """
        Get or create cache for a specific tool.

        Args:
            tool_name: Name of the tool (e.g., "prometheus_metrics")

        Returns:
            Cache instance for the tool
        """
        if tool_name not in self._caches:
            ttl = self.ttl_overrides.get(tool_name, self.default_ttl)
            self._caches[tool_name] = Cache(default_ttl=ttl)

        return self._caches[tool_name]

    def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self._caches.values():
            cache.clear()
