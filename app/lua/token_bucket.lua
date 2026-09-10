-- Token Bucket Atomic Rate Limiter
-- KEYS[1]: Token bucket hash key (e.g., rate_limit:tb:ip_127.0.0.1)
-- ARGV[1]: Bucket capacity (max burst tokens)
-- ARGV[2]: Refill rate in tokens per second
-- ARGV[3]: Current timestamp in seconds (floating point or integer)
-- ARGV[4]: Cost of this request (default 1)

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4]) or 1

-- 1. Fetch current bucket state
local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    -- 2. Add tokens accumulated since last update
    local elapsed = math.max(0, now - last_updated)
    tokens = math.min(capacity, tokens + elapsed * refill_rate)
    last_updated = now
end

if tokens >= cost then
    -- Request Allowed: consume tokens
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    -- Expire bucket if idle
    local ttl = math.ceil(capacity / refill_rate) * 2
    if ttl < 60 then ttl = 60 end
    redis.call('EXPIRE', key, ttl)
    return {1, math.floor(tokens), 0}
else
    -- Request Blocked: insufficient tokens
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    local retry_after = math.ceil((cost - tokens) / refill_rate)
    if retry_after < 1 then retry_after = 1 end
    return {0, 0, retry_after}
end
