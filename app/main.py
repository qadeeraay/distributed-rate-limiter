from contextlib import asynccontextmanager
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import settings
from app.middleware.rate_limit import DistributedRateLimitMiddleware

redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    # Ping redis
    try:
        await redis_client.ping()
    except Exception as e:
        print(f"Warning: Redis connection pending: {e}")

    yield

    if redis_client:
        await redis_client.aclose()


app = FastAPI(
    title="Distributed API Gateway Rate Limiter",
    description=(
        "Production-Grade Distributed Rate Limiting Gateway.\n\n"
        "### Core Engineering Features:\n"
        "- **Atomic Redis Lua Scripts:** Zero race-condition execution via EVALSHA\n"
        "- **Dual Algorithms:** Sliding Window Log & Token Bucket\n"
        "- **Multi-Tiered Quotas:** Anonymous, Free, Pro, Enterprise, and route-level overrides\n"
        "- **IETF Compliance:** Full RFC 6585 headers (RateLimit-Limit, Remaining, Reset, Retry-After)\n"
        "- **Fail-Open Resilience:** Circuit breaker fallback if Redis is degraded"
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Connect Redis client for middleware
app_redis = aioredis.from_url(settings.redis_url, decode_responses=False)
app.add_middleware(DistributedRateLimitMiddleware, redis_client=app_redis)


@app.get("/api/v1/public", tags=["Demonstration API"])
async def public_endpoint():
    """General public route subject to default tiered rate limits."""
    return {"status": "success", "message": "Public resource accessed."}


@app.get("/api/v1/user/profile", tags=["Demonstration API"])
async def user_profile(x_user_tier: str = Header(default="free")):
    """Tiered profile route (pass header 'X-User-Tier: pro' or 'enterprise')."""
    return {
        "status": "success",
        "tier": x_user_tier,
        "message": f"Profile accessed under tier '{x_user_tier}'."
    }


@app.post("/api/v1/checkout", tags=["Demonstration API"])
async def checkout_action():
    """Sensitive high-value route with strict security overrides."""
    return {"status": "success", "message": "Checkout initiated."}


@app.get("/healthz", tags=["Observability"])
async def healthcheck():
    """Readiness probe."""
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return {"status": "UP", "redis": "UP"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "DEGRADED", "redis": "DOWN"})


@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
