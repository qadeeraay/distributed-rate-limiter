import unittest
from app.core.policies import resolve_policy


class TestRateLimiterAlgorithms(unittest.TestCase):
    def test_tier_policy_resolution(self):
        """Verifies correct policy resolution by user tier."""
        anon_policy = resolve_policy("/api/v1/public", "anonymous")
        self.assertEqual(anon_policy.name, "anonymous")
        self.assertEqual(anon_policy.limit, 10)
        self.assertEqual(anon_policy.algorithm, "sliding_window")

        free_policy = resolve_policy("/api/v1/public", "free")
        self.assertEqual(free_policy.name, "free")
        self.assertEqual(free_policy.limit, 60)
        self.assertEqual(free_policy.algorithm, "token_bucket")

        pro_policy = resolve_policy("/api/v1/public", "pro")
        self.assertEqual(pro_policy.name, "pro")
        self.assertEqual(pro_policy.limit, 300)

        enterprise_policy = resolve_policy("/api/v1/public", "enterprise")
        self.assertEqual(enterprise_policy.name, "enterprise")
        self.assertEqual(enterprise_policy.limit, 3000)

    def test_route_override_takes_precedence(self):
        """Verifies that route-specific security policies override user tier."""
        override = resolve_policy("/api/v1/auth/login", "enterprise")
        self.assertEqual(override.name, "auth_bruteforce_guard")
        self.assertEqual(override.limit, 5)
        self.assertEqual(override.algorithm, "sliding_window")


if __name__ == "__main__":
    unittest.main()
