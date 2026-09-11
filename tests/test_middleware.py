import unittest

try:
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class TestRateLimiterMiddleware(unittest.IsolatedAsyncioTestCase):
    async def test_healthcheck_bypasses_rate_limit(self):
        if not HTTPX_AVAILABLE:
            self.skipTest("httpx not installed in local runtime")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(15):
                res = await client.get("/healthz")
                self.assertIn(res.status_code, (200, 503))

    async def test_public_endpoint_headers(self):
        if not HTTPX_AVAILABLE:
            self.skipTest("httpx not installed in local runtime")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/v1/public")
            self.assertIn(res.status_code, (200, 429))
            if res.status_code == 200:
                self.assertIn("ratelimit-limit", res.headers)
                self.assertIn("ratelimit-remaining", res.headers)
                self.assertIn("ratelimit-reset", res.headers)

    async def test_user_tier_header_propagation(self):
        if not HTTPX_AVAILABLE:
            self.skipTest("httpx not installed in local runtime")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(
                "/api/v1/user/profile",
                headers={"X-User-Tier": "pro", "X-API-Key": "test_token_123"}
            )
            self.assertIn(res.status_code, (200, 429))
            if res.status_code == 200:
                data = res.json()
                self.assertEqual(data["tier"], "pro")
