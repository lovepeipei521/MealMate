"""
Middleware module for MealMate.

Provides HTTP middleware components:
- Rate limiting
- Security headers
"""

from app.security.middleware.rate_limiter import RateLimiter, RateLimitConfig

__all__ = [
    "RateLimiter",
    "RateLimitConfig",
]
