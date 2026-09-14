from typing import Optional, Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis
from app.core.limiter import DistributedRateLimiter
from app.core.policies import resolve_policy


class DistributedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI Rate Limiting Middleware.
    Enforces atomic Redis-backed rate limits and appends IETF/RFC headers.
    """

    def __init__(
        self,
        app,
        redis_client: Optional[aioredis.Redis] = None,
        get_redis_client: Optional[Callable[[], aioredis.Redis]] = None
    ):
        super().__init__(app)
        self._redis_client = redis_client
        self._get_redis_client = get_redis_client
        self._limiter: Optional[DistributedRateLimiter] = DistributedRateLimiter(redis_client) if redis_client else None
        self._cached_client: Optional[aioredis.Redis] = redis_client

    def _resolve_limiter(self) -> DistributedRateLimiter:
        if self._get_redis_client:
            client = self._get_redis_client()
            if self._limiter is None or self._cached_client is not client:
                self._limiter = DistributedRateLimiter(client)
                self._cached_client = client
            return self._limiter
        return self._limiter

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/healthz", "/metrics", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # 1. Resolve client identifier (API Key / Token or IP)
        api_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization")

        if api_key:
            client_id = f"apikey_{api_key}"
        elif auth_header:
            client_id = f"auth_{auth_header.split(' ')[-1][:16]}"
        else:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = request.client.host if request.client else "127.0.0.1"
            client_id = f"ip_{client_ip}"

        user_tier = request.headers.get("X-User-Tier", "anonymous")
        policy = resolve_policy(request.url.path, user_tier)

        limiter = self._resolve_limiter()
        result = await limiter.check(
            identifier=f"{client_id}:{request.url.path}",
            policy=policy
        )


        # If Limit Exceeded -> Return RFC 6585 HTTP 429 Too Many Requests
        if not result.allowed:
            headers = {
                "RateLimit-Limit": str(result.limit),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(result.retry_after),
                "RateLimit-Policy": f"{result.limit};w={policy.window_seconds};algo={result.algorithm}",
                "Retry-After": str(result.retry_after)
            }
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit exceeded for policy '{policy.name}'. Please retry in {result.retry_after} seconds.",
                    "policy": policy.name,
                    "retry_after": result.retry_after
                },
                headers=headers
            )

        # Request Allowed: proceed to downstream route
        response: Response = await call_next(request)

        # Append IETF RateLimit Headers to downstream response
        response.headers["RateLimit-Limit"] = str(result.limit)
        response.headers["RateLimit-Remaining"] = str(result.remaining)
        response.headers["RateLimit-Reset"] = str(result.reset_seconds)
        response.headers["RateLimit-Policy"] = f"{result.limit};w={policy.window_seconds};algo={result.algorithm}"

        return response
