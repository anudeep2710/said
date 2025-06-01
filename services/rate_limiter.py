#!/usr/bin/env python3
"""
Rate limiting service with multiple strategies and backends
"""

import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"

@dataclass
class RateLimit:
    """Rate limit configuration"""
    requests: int
    window: int  # seconds
    strategy: RateLimitStrategy = RateLimitStrategy.FIXED_WINDOW
    burst: Optional[int] = None  # for token bucket

@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None

class RateLimiter:
    """Advanced rate limiter with multiple strategies"""
    
    def __init__(self):
        self.default_limits = {
            "global": RateLimit(1000, 3600),  # 1000 requests per hour
            "per_ip": RateLimit(100, 3600),   # 100 requests per hour per IP
            "per_user": RateLimit(500, 3600), # 500 requests per hour per user
            "upload": RateLimit(10, 3600),    # 10 uploads per hour
            "ai_query": RateLimit(50, 3600),  # 50 AI queries per hour
            "auth": RateLimit(5, 300),        # 5 auth attempts per 5 minutes
        }
        
        # Premium user limits (higher limits)
        self.premium_limits = {
            "global": RateLimit(10000, 3600),
            "per_ip": RateLimit(1000, 3600),
            "per_user": RateLimit(5000, 3600),
            "upload": RateLimit(100, 3600),
            "ai_query": RateLimit(500, 3600),
            "auth": RateLimit(10, 300),
        }
    
    async def check_rate_limit(
        self,
        identifier: str,
        limit_type: str,
        is_premium: bool = False
    ) -> RateLimitResult:
        """Check if request is within rate limit"""
        
        # Get appropriate limit configuration
        limits = self.premium_limits if is_premium else self.default_limits
        rate_limit = limits.get(limit_type, self.default_limits["global"])
        
        cache_key = f"rate_limit:{limit_type}:{identifier}"
        
        if rate_limit.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._check_fixed_window(cache_key, rate_limit)
        elif rate_limit.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._check_sliding_window(cache_key, rate_limit)
        elif rate_limit.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._check_token_bucket(cache_key, rate_limit)
        else:
            return await self._check_fixed_window(cache_key, rate_limit)
    
    async def _check_fixed_window(self, cache_key: str, rate_limit: RateLimit) -> RateLimitResult:
        """Fixed window rate limiting"""
        current_time = int(time.time())
        window_start = (current_time // rate_limit.window) * rate_limit.window
        window_key = f"{cache_key}:{window_start}"
        
        # Get current count
        current_count = await cache_service.get(window_key) or 0
        
        if current_count >= rate_limit.requests:
            reset_time = window_start + rate_limit.window
            retry_after = reset_time - current_time
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after
            )
        
        # Increment counter
        new_count = await cache_service.increment_rate_limit(window_key, rate_limit.window)
        remaining = max(0, rate_limit.requests - new_count)
        reset_time = window_start + rate_limit.window
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time
        )
    
    async def _check_sliding_window(self, cache_key: str, rate_limit: RateLimit) -> RateLimitResult:
        """Sliding window rate limiting"""
        current_time = int(time.time())
        window_start = current_time - rate_limit.window
        
        # Get timestamps of recent requests
        timestamps_key = f"{cache_key}:timestamps"
        timestamps = await cache_service.get(timestamps_key) or []
        
        # Filter out old timestamps
        recent_timestamps = [ts for ts in timestamps if ts > window_start]
        
        if len(recent_timestamps) >= rate_limit.requests:
            oldest_timestamp = min(recent_timestamps)
            retry_after = oldest_timestamp + rate_limit.window - current_time
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=oldest_timestamp + rate_limit.window,
                retry_after=max(1, retry_after)
            )
        
        # Add current timestamp
        recent_timestamps.append(current_time)
        await cache_service.set(timestamps_key, recent_timestamps, rate_limit.window)
        
        remaining = rate_limit.requests - len(recent_timestamps)
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=current_time + rate_limit.window
        )
    
    async def _check_token_bucket(self, cache_key: str, rate_limit: RateLimit) -> RateLimitResult:
        """Token bucket rate limiting"""
        current_time = time.time()
        bucket_key = f"{cache_key}:bucket"
        
        # Get current bucket state
        bucket_data = await cache_service.get(bucket_key) or {
            "tokens": rate_limit.requests,
            "last_refill": current_time
        }
        
        # Calculate tokens to add based on time elapsed
        time_elapsed = current_time - bucket_data["last_refill"]
        tokens_to_add = int(time_elapsed * (rate_limit.requests / rate_limit.window))
        
        # Refill bucket
        max_tokens = rate_limit.burst or rate_limit.requests
        bucket_data["tokens"] = min(max_tokens, bucket_data["tokens"] + tokens_to_add)
        bucket_data["last_refill"] = current_time
        
        if bucket_data["tokens"] < 1:
            retry_after = int((1 - bucket_data["tokens"]) * (rate_limit.window / rate_limit.requests))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=int(current_time + retry_after),
                retry_after=retry_after
            )
        
        # Consume token
        bucket_data["tokens"] -= 1
        await cache_service.set(bucket_key, bucket_data, rate_limit.window * 2)
        
        return RateLimitResult(
            allowed=True,
            remaining=int(bucket_data["tokens"]),
            reset_time=int(current_time + rate_limit.window)
        )
    
    async def reset_rate_limit(self, identifier: str, limit_type: str) -> bool:
        """Reset rate limit for identifier"""
        cache_key = f"rate_limit:{limit_type}:{identifier}"
        return await cache_service.delete(cache_key)
    
    def get_identifier_from_request(self, request: Request, user_id: Optional[str] = None) -> str:
        """Extract identifier from request"""
        if user_id:
            return f"user:{user_id}"
        
        # Try to get real IP from headers (for load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"
        
        # Fallback to client IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

# Global rate limiter instance
rate_limiter = RateLimiter()

# FastAPI dependency for rate limiting
async def rate_limit_dependency(
    request: Request,
    limit_type: str = "global",
    user_id: Optional[str] = None,
    is_premium: bool = False
):
    """FastAPI dependency for rate limiting"""
    identifier = rate_limiter.get_identifier_from_request(request, user_id)
    result = await rate_limiter.check_rate_limit(identifier, limit_type, is_premium)
    
    if not result.allowed:
        headers = {
            "X-RateLimit-Limit": str(rate_limiter.default_limits[limit_type].requests),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_time),
        }
        
        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)
        
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many requests for {limit_type}",
                "retry_after": result.retry_after,
                "reset_time": result.reset_time
            },
            headers=headers
        )
    
    return result

# Decorator for rate limiting
def rate_limit(limit_type: str = "global", is_premium: bool = False):
    """Decorator for rate limiting endpoints"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request and user_id from kwargs
            request = kwargs.get("request")
            user_id = kwargs.get("user_id")
            
            if request:
                await rate_limit_dependency(request, limit_type, user_id, is_premium)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Rate limiting middleware
class RateLimitMiddleware:
    """Middleware for automatic rate limiting"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Skip rate limiting for health checks
            if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
                await self.app(scope, receive, send)
                return
            
            try:
                # Apply global rate limiting
                identifier = rate_limiter.get_identifier_from_request(request)
                result = await rate_limiter.check_rate_limit(identifier, "global")
                
                if not result.allowed:
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "error": "Rate limit exceeded",
                            "message": "Too many requests",
                            "retry_after": result.retry_after
                        },
                        headers={
                            "X-RateLimit-Limit": "1000",
                            "X-RateLimit-Remaining": str(result.remaining),
                            "X-RateLimit-Reset": str(result.reset_time),
                            "Retry-After": str(result.retry_after) if result.retry_after else "60"
                        }
                    )
                    await response(scope, receive, send)
                    return
                
            except Exception as e:
                logger.error(f"Rate limiting error: {str(e)}")
                # Continue without rate limiting if there's an error
            
        await self.app(scope, receive, send)
