# QuickNode Rate Limiter Usage Guide

## Overview

The QuickNode rate limiter provides advanced rate limiting, endpoint failover, and exponential backoff to prevent API bans when monitoring multiple wallets.

## Features

- ✅ **Token Bucket Algorithm**: Smooth rate limiting with burst capacity
- ✅ **Adaptive Rate Limiting**: Automatically adjusts rate based on API responses
- ✅ **Semaphore-based Concurrency**: Max 3 concurrent requests
- ✅ **Exponential Backoff**: Handles 429 responses with intelligent retry
- ✅ **Endpoint Failover**: Automatically switches to fallback endpoints
- ✅ **Health Monitoring**: Tracks endpoint health and success rates
- ✅ **Comprehensive Logging**: Real-time rate limit status monitoring

## Configuration

### Settings

Update your `.env` file or `config/settings.py`:

```python
# Primary QuickNode endpoint
POLYGON_RPC_URL=https://your-quicknode-endpoint.com/v1/your-api-key

# Optional fallback endpoints
POLYGON_RPC_FALLBACKS=https://fallback1.com,https://fallback2.com
```

### NetworkConfig

```python
from config.settings import settings

# Access RPC endpoints
primary = settings.network.polygon_rpc_url
fallbacks = settings.network.polygon_rpc_fallbacks
```

## Usage Examples

### Basic Usage

```python
from risk_management.rate_limiter import QuickNodeRPCClient

# Initialize client
client = QuickNodeRPCClient(
    primary_endpoint="https://your-quicknode-endpoint.com/v1/your-api-key",
    fallback_endpoints=[
        "https://fallback1.com",
        "https://fallback2.com",
    ],
)

# Make RPC calls
block_number = await client.get_block_number()
balance = await client.call("eth_getBalance", ["0x...", "latest"])

# Clean up
await client.close()
```

### Integration with Wallet Monitor

```python
from risk_management.rate_limiter import QuickNodeRPCClient
from config.settings import settings

class WalletMonitor:
    def __init__(self, settings):
        self.settings = settings

        # Initialize rate-limited RPC client
        self.rpc_client = QuickNodeRPCClient(
            primary_endpoint=settings.network.polygon_rpc_url,
            fallback_endpoints=settings.network.polygon_rpc_fallbacks,
        )

    async def get_wallet_transactions(self, address: str):
        """Get transactions with rate limiting"""
        # Use eth_getLogs or similar RPC methods
        # The rate limiter handles all rate limiting automatically
        result = await self.rpc_client.call(
            "eth_getLogs",
            [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "address": address,
            }]
        )
        return result
```

### Monitoring Rate Limit Status

```python
# Get health summary
health = client.get_health_summary()

print(f"Current endpoint: {health['current_endpoint']}")
print(f"Rate: {health['rate_limiter_stats']['current_rate']} req/s")
print(f"Success rate: {health['rate_limiter_stats']['success_rate']:.1%}")

# Check endpoint health
for url, endpoint_health in health['endpoints'].items():
    print(f"{url}: {endpoint_health['status']} "
          f"(success_rate={endpoint_health['success_rate']:.1%})")
```

## Rate Limiter Behavior

### Token Bucket

- **Capacity**: 30 tokens (burst capacity)
- **Refill Rate**: Starts at 10 req/s, adapts based on responses
- **Initial Rate**: 10 requests per second
- **Max Rate**: 20 requests per second
- **Min Rate**: 1 request per second (when throttled)

### Adaptive Rate Adjustment

1. **On Rate Limit (429)**:
   - Rate cut in half immediately
   - Exponential backoff applied
   - Switches to fallback endpoint if available

2. **On Success**:
   - Gradually increases rate (1% per request)
   - Resets consecutive rate limit counter after 60s

3. **Concurrency Control**:
   - Maximum 3 concurrent requests
   - Semaphore enforces limit

## Testing

### Run Integration Tests

```bash
# Run all rate limiter tests
pytest tests/integration/test_quicknode_rate_limiter.py -v

# Run specific test (25+ wallets)
pytest tests/integration/test_quicknode_rate_limiter.py::TestRateLimiterIntegration::test_25_wallets_15_second_intervals -v

# Run with logging
pytest tests/integration/test_quicknode_rate_limiter.py -v -s --log-cli-level=INFO
```

### Test Scenarios

1. **25+ Wallets at 15-second intervals**: Verifies no rate limit bans
2. **Burst Load**: Tests handling of sudden request spikes
3. **Concurrent Request Limit**: Verifies max 3 concurrent requests
4. **Endpoint Failover**: Tests automatic switching to fallbacks
5. **Exponential Backoff**: Tests backoff calculation

## Monitoring

### Log Messages

The rate limiter logs comprehensive statistics every minute:

```
📊 Rate Limiter Stats: rate=10.50 req/s, total=150, success_rate=98.7%,
   rate_limited=2, current_endpoint=https://primary-endpoint.com
```

### Health Summary

```python
health = client.get_health_summary()

# Returns:
{
    "current_endpoint": "https://primary-endpoint.com",
    "rate_limiter_stats": {
        "current_rate": 10.5,
        "total_requests": 150,
        "successful_requests": 148,
        "rate_limited_requests": 2,
        "success_rate": 0.987,
    },
    "endpoints": {
        "https://primary-endpoint.com": {
            "status": "active",
            "success_rate": 0.99,
            "total_requests": 100,
            "avg_response_time": 0.123,
            "is_healthy": True,
        },
        # ... fallback endpoints
    }
}
```

## Best Practices

1. **Always use fallback endpoints**: Provides redundancy
2. **Monitor health summary**: Check endpoint status regularly
3. **Handle RateLimitError**: Implement retry logic for critical operations
4. **Close client on shutdown**: `await client.close()`
5. **Use appropriate intervals**: 15-second intervals work well for 25+ wallets

## Troubleshooting

### Rate Limits Still Occurring

- Check if fallback endpoints are configured
- Verify rate limiter is being used (check logs)
- Reduce initial rate if needed
- Check QuickNode plan limits

### High Error Rates

- Verify endpoint URLs are correct
- Check network connectivity
- Review endpoint health in logs
- Consider adding more fallback endpoints

### Slow Performance

- Rate limiter intentionally slows requests to prevent bans
- This is expected behavior
- Monitor success rate - should be >95%
- Adjust `max_rate` if needed (but risk rate limits)

## Migration from Polygonscan

If migrating from Polygonscan API:

1. Update `POLYGON_RPC_URL` to QuickNode endpoint
2. Add fallback endpoints to `POLYGON_RPC_FALLBACKS`
3. Replace `RateLimitedPolygonscanClient` with `QuickNodeRPCClient`
4. Update RPC method calls (eth_getLogs instead of REST API)
5. Run integration tests to verify

## Performance Expectations

With 25 wallets at 15-second intervals:
- **Success Rate**: >95%
- **Rate Limit Bans**: 0
- **Average Rate**: 10-15 req/s (adaptive)
- **Response Time**: <500ms per request
- **Concurrent Requests**: Max 3 at any time
