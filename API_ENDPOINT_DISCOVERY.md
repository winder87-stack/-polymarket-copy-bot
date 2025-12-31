# API Endpoint Discovery System

## Overview

The API endpoint discovery system automatically finds and validates working Polymarket API endpoints to ensure your copy trading bot always has access to the most reliable data sources.

## How It Works

### Weekly Discovery Process
- **Frequency**: Runs every Sunday at 00:00 via systemd timer
- **Method**: Tests 16+ potential endpoint variations
- **Validation**: Confirms endpoints return valid leaderboard data
- **Storage**: Saves results to `config/discovered_endpoints.json`

### Tested Endpoints
The discovery script systematically tests these endpoints:
- `/api/leaderboard` (primary)
- `/api/v1/leaderboard`
- `/v1/api/leaderboard`
- `/api/v2/leaderboard`
- `/leaderboard/api`
- `/data/leaderboard`
- `/analytics/leaderboard`
- `/market/leaderboard`
- `/trader/leaderboard`
- `/api/performance`
- `/api/traders`
- `/api/top-traders`
- `/api/rankings`
- `/api/user-rankings`
- `/api/market-makers`
- `/graphql` (POST method)

## Setup Instructions

### 1. Initial Setup
```bash
# Make scripts executable
chmod +x scripts/discover_api_endpoints.py
chmod +x scripts/setup_api_discovery_cron.sh

# Run initial discovery
./scripts/discover_api_endpoints.py
```

### 2. Automated Cron Setup
```bash
# Setup systemd timer for weekly execution
sudo ./scripts/setup_api_discovery_cron.sh
```

This creates:
- Systemd service: `polymarket-api-discovery.service`
- Systemd timer: `polymarket-api-discovery.timer`
- Log rotation: `/etc/logrotate.d/polymarket-api-discovery`

### 3. Manual Execution
```bash
# Run discovery manually
sudo systemctl start polymarket-api-discovery.service

# Check status
sudo systemctl status polymarket-api-discovery.timer
sudo systemctl list-timers | grep polymarket
```

## Output Files

### discovered_endpoints.json
```json
{
  "discovery_time": 1703123456.789,
  "working_endpoints": [
    {
      "endpoint": "/api/leaderboard",
      "method": "GET",
      "status": "working",
      "response_keys": ["data", "meta", "pagination"]
    },
    {
      "endpoint": "/graphql",
      "method": "POST",
      "status": "working",
      "type": "graphql"
    }
  ],
  "recommendations": {
    "endpoint": "/api/leaderboard",
    "method": "GET",
    "status": "working"
  }
}
```

## Integration with Main Bot

The discovery results are automatically used by the fallback system:

1. **Primary API fails** → Check `discovered_endpoints.json`
2. **Use recommended endpoint** → Update Polymarket API client
3. **Fallback to community wallets** → If all discovered endpoints fail

## Monitoring

### Logs
- **Location**: `/var/log/polymarket-bot/api_discovery.log`
- **Rotation**: Weekly with 4-week retention
- **Format**: Timestamped output from discovery script

### Alerts
The system integrates with your existing alert system:
- **Success**: Logs working endpoints found
- **Failure**: Alerts if no endpoints discovered
- **Changes**: Notifies when new endpoints are found

## Troubleshooting

### No Endpoints Found
```bash
# Check network connectivity
curl -I https://polymarket.com

# Verify API key
grep POLYMARKET_API_KEY config/settings.py

# Run with verbose output
./scripts/discover_api_endpoints.py
```

### Cron Job Not Running
```bash
# Check timer status
sudo systemctl status polymarket-api-discovery.timer

# Check service logs
sudo journalctl -u polymarket-api-discovery.service -f

# Restart timer
sudo systemctl restart polymarket-api-discovery.timer
```

### Permission Issues
```bash
# Fix permissions
sudo chown -R polymarket:polymarket /home/polymarket/polymarket-copy-bot
sudo chmod 755 scripts/discover_api_endpoints.py
```

## Benefits

1. **Proactive Endpoint Discovery**: Finds working endpoints before they break
2. **Automated Updates**: Weekly checks keep endpoint knowledge current
3. **Fallback Reliability**: Multiple backup endpoints ensure continuity
4. **Reduced Downtime**: Automatic endpoint switching minimizes impact
5. **Production Hardened**: Systemd integration ensures reliable execution

## Security Considerations

- Rate limiting: 1-second delays between endpoint tests
- User-Agent identification for proper API usage
- No sensitive data logging
- Secure file permissions on discovery results
