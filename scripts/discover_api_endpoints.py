#!/usr/bin/env python3
"""
API endpoint discovery script - run weekly to find working Polymarket endpoints
"""

import requests
import json
import time
import os
from config.scanner_config import ScannerConfig


def discover_working_endpoints():
    """Systematically test potential Polymarket API endpoints"""
    config = ScannerConfig()
    base_url = "https://polymarket.com"

    # Comprehensive endpoint list to test
    potential_endpoints = [
        "/api/leaderboard",
        "/api/v1/leaderboard",
        "/v1/api/leaderboard",
        "/api/v2/leaderboard",
        "/leaderboard/api",
        "/data/leaderboard",
        "/analytics/leaderboard",
        "/market/leaderboard",
        "/trader/leaderboard",
        "/api/performance",
        "/api/traders",
        "/api/top-traders",
        "/api/rankings",
        "/api/user-rankings",
        "/api/market-makers",
        "/graphql",  # GraphQL endpoint (different approach)
    ]

    headers = {
        "User-Agent": "PolymarketCopyBot/1.0",
        "Accept": "application/json",
        "Authorization": f"Bearer {config.POLYMARKET_API_KEY}"
        if config.POLYMARKET_API_KEY
        else "",
        "Content-Type": "application/json",
    }

    working_endpoints = []

    print("🔍 Discovering working Polymarket API endpoints...")
    print("══════════════════════════════════════════════════")

    for endpoint in potential_endpoints:
        print(f"\nTesting: {endpoint}")
        try:
            # Test both GET and POST methods
            url = f"{base_url}{endpoint}"

            # Test GET request
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
                params={"limit": 5, "timeframe": "30d", "sortBy": "roi"},
            )

            print(f"  GET Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        print(
                            f"  ✅ GET returned valid data ({len(data['data'])} records)"
                        )
                        working_endpoints.append(
                            {
                                "endpoint": endpoint,
                                "method": "GET",
                                "status": "working",
                                "response_keys": list(data.keys())[:5],
                            }
                        )
                except json.JSONDecodeError:
                    print("  ❌ GET returned invalid JSON")

            elif response.status_code != 404:
                print(f"  ⚠️ GET returned unexpected status: {response.status_code}")

            # Test POST request (for GraphQL endpoint)
            if endpoint == "/graphql":
                graphql_query = {
                    "query": """
                    query GetLeaderboard($limit: Int!, $timeframe: String!) {
                        leaderboard(limit: $limit, timeframe: $timeframe) {
                            address
                            roi
                            winRate
                            tradeCount
                            lastTrade
                        }
                    }
                    """,
                    "variables": {"limit": 5, "timeframe": "30d"},
                }

                response = requests.post(
                    url, headers=headers, json=graphql_query, timeout=10
                )
                print(f"  POST Status: {response.status_code}")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("data", {}).get("leaderboard"):
                            print("  ✅ POST returned valid leaderboard data")
                            working_endpoints.append(
                                {
                                    "endpoint": endpoint,
                                    "method": "POST",
                                    "status": "working",
                                    "type": "graphql",
                                }
                            )
                    except json.JSONDecodeError:
                        print("  ❌ POST returned invalid JSON")

        except Exception as e:
            print(f"  ❌ Error testing {endpoint}: {str(e)[:100]}")

        time.sleep(1)  # Be respectful to their servers

    # Save results
    if working_endpoints:
        print(f"\n🎉 Found {len(working_endpoints)} working endpoints:")
        for endpoint in working_endpoints:
            print(f"  • {endpoint['endpoint']} ({endpoint['method']})")

        # Create config directory if it doesn't exist
        os.makedirs("config", exist_ok=True)

        # Update configuration file
        with open("config/discovered_endpoints.json", "w") as f:
            json.dump(
                {
                    "discovery_time": time.time(),
                    "working_endpoints": working_endpoints,
                    "recommendations": working_endpoints[0]
                    if working_endpoints
                    else None,  # Use first working as primary
                },
                f,
                indent=2,
            )

        print("✅ Results saved to config/discovered_endpoints.json")
    else:
        print(
            "❌ No working endpoints found. Check network connectivity and API key validity."
        )


if __name__ == "__main__":
    discover_working_endpoints()

# Add to cron job for weekly execution
# 0 2 * * 0 /path/to/polymarket-copy-bot/scripts/discover_api_endpoints.py >> /var/log/api_discovery.log 2>&1
