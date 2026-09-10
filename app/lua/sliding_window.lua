-- Sliding Window Log Atomic Rate Limiter
-- KEYS[1]: Rate limit key (e.g., rate_limit:sliding:ip_127.0.0.1)
-- ARGV[1]: Current timestamp in milliseconds
-- ARGV[2]: Window size in milliseconds
-- ARGV[3]: Max requests allowed in window

local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window

-- 1. Remove timestamps outside the active rolling window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

-- 2. Count requests currently recorded within the window
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    -- Request Allowed
    redis.call('ZADD', key, now, now)
    redis.call('PEXPIRE', key, window)
    local remaining = limit - current_requests - 1
    return {1, remaining, math.ceil(window / 1000)}
else
    -- Request Blocked (Limit Exceeded)
    -- Compute earliest expiring request to determine retry-after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest and #oldest >= 2 then
        local oldest_time = tonumber(oldest[2])
        retry_after = math.ceil((oldest_time + window - now) / 1000)
        if retry_after < 1 then retry_after = 1 end
    end
    return {0, 0, retry_after}
end
