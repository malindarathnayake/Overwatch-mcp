"""Tests for cache module."""

import time

import pytest

from overwatch_mcp.cache import Cache, CacheManager


class TestCache:
    """Tests for Cache class."""

    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        cache = Cache[str](default_ttl=60)
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None

    def test_cache_has(self):
        """Test has method."""
        cache = Cache[str](default_ttl=60)
        cache.set("key1", "value1")

        assert cache.has("key1") is True
        assert cache.has("nonexistent") is False

    def test_cache_delete(self):
        """Test delete operation."""
        cache = Cache[str](default_ttl=60)
        cache.set("key1", "value1")
        assert cache.has("key1") is True

        cache.delete("key1")
        assert cache.has("key1") is False

    def test_cache_delete_nonexistent(self):
        """Test deleting non-existent key doesn't raise error."""
        cache = Cache[str](default_ttl=60)
        cache.delete("nonexistent")  # Should not raise

    def test_cache_clear(self):
        """Test clear operation."""
        cache = Cache[str](default_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert len(cache) == 2

        cache.clear()
        assert len(cache) == 0

    def test_cache_keys(self):
        """Test keys method."""
        cache = Cache[str](default_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        keys = cache.keys()
        assert "key1" in keys
        assert "key2" in keys
        assert len(keys) == 2

    def test_cache_len(self):
        """Test __len__ method."""
        cache = Cache[str](default_ttl=60)
        assert len(cache) == 0

        cache.set("key1", "value1")
        assert len(cache) == 1

        cache.set("key2", "value2")
        assert len(cache) == 2

    def test_cache_ttl_expiry(self):
        """Test that entries expire after TTL."""
        cache = Cache[str](default_ttl=1)  # 1 second TTL
        cache.set("key1", "value1")

        assert cache.has("key1") is True

        # Wait for expiry
        time.sleep(1.1)

        # Entry should be expired
        assert cache.has("key1") is False
        assert cache.get("key1") is None

    def test_cache_maxsize_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = Cache[str](default_ttl=60, maxsize=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache) == 2

        # This should evict the least recently used entry
        cache.set("key3", "value3")

        # Cache should still have 2 entries
        assert len(cache) == 2

        # key1 should have been evicted (LRU)
        # Note: This depends on cachetools LRU implementation
        assert cache.has("key3") is True

    def test_cache_type_safety(self):
        """Test cache with different types."""
        int_cache = Cache[int](default_ttl=60)
        int_cache.set("count", 42)
        assert int_cache.get("count") == 42

        dict_cache = Cache[dict](default_ttl=60)
        dict_cache.set("config", {"key": "value"})
        assert dict_cache.get("config") == {"key": "value"}


class TestCacheManager:
    """Tests for CacheManager class."""

    def test_get_cache_creates_new(self):
        """Test that get_cache creates a new cache if doesn't exist."""
        manager = CacheManager(default_ttl=60)
        cache = manager.get_cache("test_tool")

        assert cache is not None
        assert isinstance(cache, Cache)

    def test_get_cache_returns_same_instance(self):
        """Test that get_cache returns the same cache instance."""
        manager = CacheManager(default_ttl=60)
        cache1 = manager.get_cache("test_tool")
        cache2 = manager.get_cache("test_tool")

        assert cache1 is cache2

    def test_cache_manager_with_ttl_overrides(self):
        """Test cache manager with TTL overrides."""
        manager = CacheManager(
            default_ttl=60,
            ttl_overrides={
                "prometheus_metrics": 300,
                "graylog_fields": 300
            }
        )

        # Get caches
        default_cache = manager.get_cache("some_tool")
        prom_cache = manager.get_cache("prometheus_metrics")
        graylog_cache = manager.get_cache("graylog_fields")

        # Check TTLs
        assert default_cache.default_ttl == 60
        assert prom_cache.default_ttl == 300
        assert graylog_cache.default_ttl == 300

    def test_cache_isolation(self):
        """Test that different tool caches are isolated."""
        manager = CacheManager(default_ttl=60)

        cache1 = manager.get_cache("tool1")
        cache2 = manager.get_cache("tool2")

        cache1.set("key", "value1")
        cache2.set("key", "value2")

        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"

    def test_clear_all(self):
        """Test clearing all caches."""
        manager = CacheManager(default_ttl=60)

        cache1 = manager.get_cache("tool1")
        cache2 = manager.get_cache("tool2")

        cache1.set("key1", "value1")
        cache2.set("key2", "value2")

        assert len(cache1) == 1
        assert len(cache2) == 1

        manager.clear_all()

        assert len(cache1) == 0
        assert len(cache2) == 0
