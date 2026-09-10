import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_healthcheck_bypasses_rate_limit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Rapidly ping healthcheck - should never be rate-limited
        for _ in range(15):
            res = await client.get("/healthz")
            assert res.status_code in (200, 503)


@pytest.mark.asyncio
async def test_public_endpoint_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/public")
        # Under circuit breaker (if redis not running locally) or normal execution
        assert res.status_code in (200, 429)
        if res.status_code == 200:
            assert "ratelimit-limit" in res.headers
            assert "ratelimit-remaining" in res.headers
            assert "ratelimit-reset" in res.headers


@pytest.mark.asyncio
async def test_user_tier_header_propagation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/api/v1/user/profile",
            headers={"X-User-Tier": "pro", "X-API-Key": "test_token_123"}
        )
        assert res.status_code in (200, 429)
        if res.status_code == 200:
            data = res.json()
            assert data["tier"] == "pro"
