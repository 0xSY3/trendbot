from cachetools import TTLCache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Shared caching mechanism for news fetchers
    """
    def __init__(self, cache_ttl_hours=8):
        self.cache_ttl = timedelta(hours=cache_ttl_hours).total_seconds()
        self.cache = TTLCache(maxsize=100, ttl=self.cache_ttl)

    def get(self, key):
        """Get value from cache"""
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None

    def set(self, key, value):
        """Set value in cache"""
        try:
            self.cache[key] = value
            return True
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False

    def get_cache_status(self):
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "ttl_hours": self.cache_ttl / 3600,
            "currsize": len(self.cache)
        }