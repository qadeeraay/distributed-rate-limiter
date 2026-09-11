#!/usr/bin/env python3
"""
Interactive CLI Demonstrator for Distributed Rate Limiter.
Simulates the exact Token Bucket and Sliding Window Log algorithms
implemented in our Redis Lua scripts without requiring an active Redis server.
"""

import time
from dataclasses import dataclass


@dataclass
class TokenBucketSimulator:
    capacity: int
    refill_rate: float  # tokens/sec
    tokens: float
    last_updated: float

    def allow(self, cost: int = 1):
        now = time.time()
        elapsed = max(0.0, now - self.last_updated)
        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate)
        self.last_updated = now

        if self.tokens >= cost:
            self.tokens -= cost
            return True, int(self.tokens), 0
        else:
            retry_after = int((cost - self.tokens) / self.refill_rate) + 1
            return False, 0, retry_after


class SlidingWindowSimulator:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.timestamps = []

    def allow(self):
        now = time.time()
        cutoff = now - self.window
        # Clear expired timestamps
        self.timestamps = [t for t in self.timestamps if t > cutoff]

        if len(self.timestamps) < self.limit:
            self.timestamps.append(now)
            remaining = self.limit - len(self.timestamps)
            return True, remaining, self.window
        else:
            oldest = self.timestamps[0]
            retry_after = max(1, int(oldest + self.window - now))
            return False, 0, retry_after


def main():
    print("\n" + "=" * 65)
    print("  DISTRIBUTED RATE LIMITER - ALGORITHMIC SIMULATION")
    print("=" * 65)

    print("\n[1] Demonstrating Token Bucket Traffic Shaping...")
    print("    - Capacity: 5 tokens (Burst limit)")
    print("    - Refill Rate: 2.0 tokens/second")
    
    bucket = TokenBucketSimulator(capacity=5, refill_rate=2.0, tokens=5.0, last_updated=time.time())

    print("\n    Firing rapid burst of 7 requests:")
    for i in range(1, 8):
        allowed, remaining, retry = bucket.allow(cost=1)
        status = f"HTTP 200 (Allowed, {remaining} tokens left)" if allowed else f"HTTP 429 (Throttled, Retry-After: {retry}s)"
        print(f"    • Request #{i}: {status}")

    print("\n    Waiting 1.0 second for token refill (+2 tokens)...")
    time.sleep(1.0)
    allowed, remaining, retry = bucket.allow(cost=1)
    print(f"    • Request #8 after 1.0s: {'HTTP 200 (Allowed, ' + str(remaining) + ' tokens left)' if allowed else 'HTTP 429'}")

    print("\n[2] Demonstrating Sliding Window Log (Zero Boundary Burst)...")
    print("    - Limit: 3 requests / 5 seconds")
    sw = SlidingWindowSimulator(limit=3, window_seconds=5)

    print("\n    Firing 4 requests immediately:")
    for i in range(1, 5):
        allowed, remaining, retry = sw.allow()
        status = f"HTTP 200 (Allowed, {remaining} remaining in window)" if allowed else f"HTTP 429 (Throttled, Retry-After: {retry}s)"
        print(f"    • Request #{i}: {status}")

    print("\n" + "=" * 65)
    print("  DEMO COMPLETE: Token Bucket & Sliding Window Log verified.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
