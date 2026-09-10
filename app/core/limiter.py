import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import redis.asyncio as aioredis
from app.config import settings
from app.core.policies import RatePolicy

logger = logging.getLogger("DistributedRateLimiter")


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int
    algorithm: str


class DistributedRateLimiter:
    """
    Production-Grade Distributed Rate Limiting Engine.
    Executes atomic Token Bucket & Sliding Window Log algorithms via Redis EVALSHA.
    Includes fail-open circuit breaking to preserve upstream availability if Redis is degraded.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._sliding_window_sha: Optional[str] = None
        self._token_bucket_sha: Optional[str] = None

    async def initialize_scripts(self):
        """Preloads Lua scripts into Redis script cache to use fast EVALSHA."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lua_dir = os.path.join(base_dir, "lua")

        with open(os.path.join(lua_dir, "sliding_window.lua"), "r") as f:
            sliding_script = f.read()
        self._sliding_window_sha = await self.redis.script_load(sliding_script)

        with open(os.path.join(lua_dir, "token_bucket.lua"), "r") as f:
            tb_script = f.read()
        self._token_bucket_sha = await self.redis.script_load(tb_script)

    async def check(
        self,
        identifier: str,
        policy: RatePolicy,
        cost: int = 1
    ) -> RateLimitResult:
        """
        Atomically checks and consumes quota for a given identifier against a policy.
        """
        if not self._sliding_window_sha or not self._token_bucket_sha:
            await self.initialize_scripts()

        try:
            if policy.algorithm == "token_bucket":
                return await self._check_token_bucket(identifier, policy, cost)
            else:
                return await self._check_sliding_window(identifier, policy)
        except Exception as ex:
            logger.error(f"Redis rate limit check failed: {ex}")
            if settings.CIRCUIT_BREAKER_FAIL_OPEN:
                # Fail-open: allow traffic during redis disruption, log alert
                return RateLimitResult(
                    allowed=True,
                    limit=policy.limit,
                    remaining=1,
                    reset_seconds=0,
                    retry_after=0,
                    algorithm=policy.algorithm
                )
            raise

    async def _check_sliding_window(self, identifier: str, policy: RatePolicy) -> RateLimitResult:
        key = f"rate_limit:sliding:{identifier}"
        now_ms = int(time.time() * 1000)
        window_ms = policy.window_seconds * 1000

        res = await self.redis.evalsha(
            self._sliding_window_sha,
            1,
            key,
            now_ms,
            window_ms,
            policy.limit
        )

        allowed = bool(res[0] == 1)
        remaining = int(res[1])
        retry_after = int(res[2])

        return RateLimitResult(
            allowed=allowed,
            limit=policy.limit,
            remaining=remaining,
            reset_seconds=policy.window_seconds,
            retry_after=retry_after,
            algorithm="sliding_window"
        )

    async def _check_token_bucket(self, identifier: str, policy: RatePolicy, cost: int) -> RateLimitResult:
        key = f"rate_limit:tb:{identifier}"
        now_sec = time.time()

        res = await self.redis.evalsha(
            self._token_bucket_sha,
            1,
            key,
            policy.limit,        # capacity
            policy.refill_rate,  # refill per second
            now_sec,
            cost
        )

        allowed = bool(res[0] == 1)
        remaining = int(res[1])
        retry_after = int(res[2])

        return RateLimitResult(
            allowed=allowed,
            limit=policy.limit,
            remaining=remaining,
            reset_seconds=int(policy.limit / policy.refill_rate),
            retry_after=retry_after,
            algorithm="token_bucket"
        )
