#!/usr/bin/env python3
"""
Caching service with Redis primary and in-memory fallback
"""

import os
import json
import hashlib
import logging
from typing import Any, Optional, Dict, Union
from datetime import datetime, timedelta
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from services.secret_manager import get_redis_url

logger = logging.getLogger(__name__)

class InMemoryCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cleanup_task = None
        
    async def initialize(self):
        """Initialize in-memory cache"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        logger.info("In-memory cache initialized")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._cache:
            entry = self._cache[key]
            if entry['expires_at'] > datetime.utcnow():
                return entry['value']
            else:
                del self._cache[key]
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at
            }
            return True
        except Exception as e:
            logger.error(f"Failed to set cache key '{key}': {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        return await self.get(key) is not None
    
    async def clear(self) -> bool:
        """Clear all cache entries"""
        self._cache.clear()
        return True
    
    async def _cleanup_expired(self):
        """Background task to clean up expired entries"""
        while True:
            try:
                current_time = datetime.utcnow()
                expired_keys = [
                    key for key, entry in self._cache.items()
                    if entry['expires_at'] <= current_time
                ]
                for key in expired_keys:
                    del self._cache[key]
                
                await asyncio.sleep(300)  # Clean up every 5 minutes
            except Exception as e:
                logger.error(f"Cache cleanup error: {str(e)}")
                await asyncio.sleep(60)

class RedisCache:
    """Redis-based cache implementation"""
    
    def __init__(self):
        self.redis_url = get_redis_url() or os.getenv("REDIS_URL")
        self.client = None
        
    async def initialize(self):
        """Initialize Redis connection"""
        if not self.redis_url:
            raise ValueError("Redis URL not configured")
        
        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            await self.client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get cache key '{key}': {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in Redis cache with TTL"""
        try:
            serialized_value = json.dumps(value, default=str)
            await self.client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Failed to set cache key '{key}': {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache"""
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete cache key '{key}': {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache"""
        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to check cache key '{key}': {str(e)}")
            return False
    
    async def clear(self) -> bool:
        """Clear all cache entries"""
        try:
            await self.client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """Increment a counter in cache"""
        try:
            pipe = self.client.pipeline()
            pipe.incr(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Failed to increment cache key '{key}': {str(e)}")
            return 0

class CacheService:
    """Main cache service with automatic fallback"""
    
    def __init__(self):
        self.primary_cache = None
        self.fallback_cache = None
        self.current_cache = None
        
    async def initialize(self):
        """Initialize cache with fallback strategy"""
        # Try Redis first
        if REDIS_AVAILABLE and (get_redis_url() or os.getenv("REDIS_URL")):
            try:
                self.primary_cache = RedisCache()
                await self.primary_cache.initialize()
                self.current_cache = self.primary_cache
                logger.info("Using Redis as primary cache")
                return
            except Exception as e:
                logger.warning(f"Redis initialization failed: {str(e)}")
        
        # Fallback to in-memory cache
        self.fallback_cache = InMemoryCache()
        await self.fallback_cache.initialize()
        self.current_cache = self.fallback_cache
        logger.info("Using in-memory cache as fallback")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return await self.current_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        return await self.current_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        return await self.current_cache.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        return await self.current_cache.exists(key)
    
    async def clear(self) -> bool:
        """Clear all cache entries"""
        return await self.current_cache.clear()
    
    def get_cache_type(self) -> str:
        """Get current cache type"""
        if isinstance(self.current_cache, RedisCache):
            return "redis"
        elif isinstance(self.current_cache, InMemoryCache):
            return "memory"
        else:
            return "unknown"
    
    # Specialized cache methods
    async def cache_ai_response(self, query_hash: str, response: Any, ttl: int = 3600) -> bool:
        """Cache AI response with specific TTL"""
        cache_key = f"ai_response:{query_hash}"
        return await self.set(cache_key, response, ttl)
    
    async def get_cached_ai_response(self, query_hash: str) -> Optional[Any]:
        """Get cached AI response"""
        cache_key = f"ai_response:{query_hash}"
        return await self.get(cache_key)
    
    async def cache_document_summary(self, document_id: str, summary: Any, ttl: int = 7200) -> bool:
        """Cache document summary"""
        cache_key = f"summary:{document_id}"
        return await self.set(cache_key, summary, ttl)
    
    async def get_cached_document_summary(self, document_id: str) -> Optional[Any]:
        """Get cached document summary"""
        cache_key = f"summary:{document_id}"
        return await self.get(cache_key)
    
    async def cache_user_session(self, user_id: str, session_data: Any, ttl: int = 1800) -> bool:
        """Cache user session data"""
        cache_key = f"session:{user_id}"
        return await self.set(cache_key, session_data, ttl)
    
    async def get_cached_user_session(self, user_id: str) -> Optional[Any]:
        """Get cached user session"""
        cache_key = f"session:{user_id}"
        return await self.get(cache_key)
    
    async def increment_rate_limit(self, identifier: str, window: int = 3600) -> int:
        """Increment rate limit counter"""
        if isinstance(self.current_cache, RedisCache):
            cache_key = f"rate_limit:{identifier}"
            return await self.current_cache.increment(cache_key, 1, window)
        else:
            # Fallback for in-memory cache
            cache_key = f"rate_limit:{identifier}"
            current = await self.get(cache_key) or 0
            new_value = current + 1
            await self.set(cache_key, new_value, window)
            return new_value

# Utility functions
def generate_cache_key(*args) -> str:
    """Generate a cache key from arguments"""
    key_string = ":".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

def generate_query_hash(document_id: str, query: str, **kwargs) -> str:
    """Generate a hash for AI query caching"""
    query_data = {
        "document_id": document_id,
        "query": query,
        **kwargs
    }
    query_string = json.dumps(query_data, sort_keys=True)
    return hashlib.sha256(query_string.encode()).hexdigest()

# Global cache service instance
cache_service = CacheService()
