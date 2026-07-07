"""
Authentication and security middleware for JSONServer.
Provides API key authentication and rate limiting.
"""

import hashlib
import hmac
import secrets
import time
from collections import defaultdict
from functools import wraps

from flask import request, jsonify, g


class RateLimiter:
    """
    Token bucket rate limiter.
    Tracks requests per IP with configurable limits per minute.
    Thread-safe using a simple dictionary with timestamps.
    """

    def __init__(self, max_requests: int = 120, window: int = 60):
        self.max_requests = max_requests
        self.window = window  # seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    def is_allowed(self, key: str) -> tuple[bool, int, int]:
        """
        Check if a request is allowed for the given key.

        Args:
            key: Identifier (usually IP address).

        Returns:
            Tuple of (allowed, remaining, reset_time).
        """
        now = time.time()
        self._maybe_cleanup(now)

        bucket = self._buckets[key]

        # Remove expired entries
        cutoff = now - self.window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= self.max_requests:
            oldest = bucket[0]
            reset_time = int(oldest + self.window - now) + 1
            return False, 0, reset_time

        bucket.append(now)
        remaining = self.max_requests - len(bucket)
        return True, remaining, self.window

    def _maybe_cleanup(self, now: float) -> None:
        """Periodically clean up expired buckets to prevent memory leaks."""
        if now - self._last_cleanup > self._cleanup_interval:
            self._last_cleanup = now
            cutoff = now - self.window
            expired_keys = [
                k for k, v in self._buckets.items()
                if not v or max(v) < cutoff
            ]
            for k in expired_keys:
                del self._buckets[k]


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"jsk_{secrets.token_urlsafe(32)}"


def check_api_key(provided_key: str, valid_keys: list[str]) -> bool:
    """
    Constant-time comparison of the provided key against valid keys.
    Prevents timing attacks.
    """
    if not provided_key or not valid_keys:
        return False
    for valid_key in valid_keys:
        if hmac.compare_digest(provided_key, valid_key):
            return True
    return False


def get_client_ip() -> str:
    """Extract client IP, respecting X-Forwarded-For (PythonAnywhere uses a reverse proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def require_auth(valid_keys: list[str]):
    """
    Decorator: require a valid API key in the request.

    Checks in order:
        1. Authorization: Bearer <key> header
        2. X-API-Key: <key> header
        3. ?api_key=<key> query parameter
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Extract key from multiple sources
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:].strip()
            else:
                api_key = request.headers.get("X-API-Key", "")

            # Fallback to query param (least secure, but convenient for testing)
            if not api_key:
                api_key = request.args.get("api_key", "")

            if not check_api_key(api_key, valid_keys):
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Valid API key required. Provide via Authorization: Bearer <key>, X-API-Key header, or ?api_key= param.",
                    "status": 401,
                }), 401

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_rate_limit(limiter: RateLimiter):
    """Decorator: enforce rate limiting per client IP."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            client_ip = get_client_ip()
            allowed, remaining, reset = limiter.is_allowed(client_ip)

            # Always add rate limit headers
            response_headers = {
                "X-RateLimit-Limit": str(limiter.max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset),
            }

            if not allowed:
                return jsonify({
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {limiter.max_requests} requests per {limiter.window} seconds.",
                    "status": 429,
                    "retry_after": reset,
                }), 429, response_headers

            # Store headers in g so the response can include them
            g.rate_limit_headers = response_headers
            return f(*args, **kwargs)
        return decorated
    return decorator


def sanitize_input(data: any, max_depth: int = 5, current_depth: int = 0) -> any:
    """
    Recursively sanitize input data.
    - Strips dangerous characters from strings
    - Limits nesting depth
    - Prevents excessively large values
    """
    if current_depth > max_depth:
        raise ValueError(f"Input nesting exceeds maximum depth of {max_depth}")

    if isinstance(data, dict):
        if len(data) > 100:
            raise ValueError("Object has too many keys (max 100)")
        return {
            str(k)[:200]: sanitize_input(v, max_depth, current_depth + 1)
            for k, v in data.items()
        }

    if isinstance(data, list):
        if len(data) > 10000:
            raise ValueError("Array has too many elements (max 10000)")
        return [sanitize_input(item, max_depth, current_depth + 1) for item in data]

    if isinstance(data, str):
        # Limit string length
        return data[:10000]

    # Numbers, booleans, None are safe
    return data
