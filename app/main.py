import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import settings
from app.middleware.rate_limit import DistributedRateLimitMiddleware

logger = logging.getLogger("rate_limiter")

_redis_pool: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis_pool


async def close_redis_pool() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_redis_client()
    try:
        await client.ping()
    except Exception as err:
        logger.warning("Initial Redis connection check deferred: %s", err)

    yield

    await close_redis_pool()


app = FastAPI(
    title="Distributed API Gateway Rate Limiter",
    description="Distributed rate limiting gateway enforcing atomic Token Bucket and Sliding Window policies with IETF header compliance.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(DistributedRateLimitMiddleware, redis_client=get_redis_client())


@app.get("/api/v1/public", tags=["API Gateway"])
async def public_endpoint():
    return {"status": "success", "message": "Public resource accessed."}


@app.get("/api/v1/user/profile", tags=["API Gateway"])
async def user_profile(x_user_tier: str = Header(default="free")):
    return {
        "status": "success",
        "tier": x_user_tier,
        "message": f"Profile accessed under tier '{x_user_tier}'."
    }


@app.post("/api/v1/checkout", tags=["API Gateway"])
async def checkout_action():
    return {"status": "success", "message": "Checkout initiated."}


@app.get("/healthz", tags=["Observability"])
async def healthcheck():
    try:
        client = get_redis_client()
        await client.ping()
        return {"status": "UP", "redis": "UP"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "DEGRADED", "redis": "DOWN"})


@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

