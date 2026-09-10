from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class RatePolicy:
    name: str
    algorithm: str       # "sliding_window" or "token_bucket"
    limit: int           # Max requests or bucket capacity
    window_seconds: int  # Window size in seconds (for sliding window)
    refill_rate: float   # Tokens per second (for token bucket)


# Multi-Tier Default Quotas
TIER_POLICIES: Dict[str, RatePolicy] = {
    "anonymous": RatePolicy(
        name="anonymous",
        algorithm="sliding_window",
        limit=10,
        window_seconds=60,
        refill_rate=10.0 / 60.0
    ),
    "free": RatePolicy(
        name="free",
        algorithm="token_bucket",
        limit=60,
        window_seconds=60,
        refill_rate=1.0  # 1 token per second
    ),
    "pro": RatePolicy(
        name="pro",
        algorithm="token_bucket",
        limit=300,
        window_seconds=60,
        refill_rate=5.0  # 5 tokens per second
    ),
    "enterprise": RatePolicy(
        name="enterprise",
        algorithm="token_bucket",
        limit=3000,
        window_seconds=60,
        refill_rate=50.0 # 50 tokens per second
    )
}

# Route-specific sensitivity overrides
ROUTE_OVERRIDE_POLICIES: Dict[str, RatePolicy] = {
    "/api/v1/auth/login": RatePolicy(
        name="auth_bruteforce_guard",
        algorithm="sliding_window",
        limit=5,
        window_seconds=60,
        refill_rate=5.0 / 60.0
    ),
    "/api/v1/checkout": RatePolicy(
        name="checkout_guard",
        algorithm="sliding_window",
        limit=10,
        window_seconds=60,
        refill_rate=10.0 / 60.0
    )
}


def resolve_policy(path: str, user_tier: Optional[str] = None) -> RatePolicy:
    """
    Resolves the appropriate rate limiting policy based on route overrides and user tier.
    """
    # 1. Check specific route override first
    if path in ROUTE_OVERRIDE_POLICIES:
        return ROUTE_OVERRIDE_POLICIES[path]

    # 2. Check user tier
    tier = (user_tier or "anonymous").lower()
    return TIER_POLICIES.get(tier, TIER_POLICIES["anonymous"])
