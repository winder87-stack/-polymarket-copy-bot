#!/usr/bin/env python3
"""
Polymarket API Endpoint System Demo
Demonstrates the new dynamic API endpoint system with fallbacks
"""

import os
import sys
import time
import requests
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simple logger setup
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockScannerConfig:
    """Mock configuration for demo"""

    def __init__(self):
        self.API_ENDPOINTS = [
            "https://polymarket.com/api/v1/leaderboard",  # Primary (updated)
            "https://polymarket.com/api/leaderboard",      # Fallback (original)
            "https://polymarket.com/v1/leaderboard",       # Alternative
            "https://polymarket.com/leaderboard"           # Last resort
        ]
        self.USE_TESTNET = False
        self.API_TIMEOUT = 30  # seconds
        self.POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")

class PolymarketLeaderboardAPI:
    """Demo API client showing new endpoint system"""

    def __init__(self, config: MockScannerConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolymarketCopyBot/1.1',
            'Accept': 'application/json',
            'Authorization': f'Bearer {config.POLYMARKET_API_KEY}' if config.POLYMARKET_API_KEY else ''
        })
        self.last_request_time = 0
        self.rate_limit_delay = 1.0
        self.max_retries = 3
        self.current_endpoint_index = 0

    def _respect_rate_limits(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _get_next_endpoint(self) -> str:
        """Rotate through endpoints on failure"""
        endpoint = self.config.API_ENDPOINTS[self.current_endpoint_index]
        self.current_endpoint_index = (self.current_endpoint_index + 1) % len(self.config.API_ENDPOINTS)
        return endpoint

    def _get_fallback_wallets(self) -> List[Dict[str, Any]]:
        """Emergency fallback wallet list"""
        return [
            {
                'address': '0x742d35Cc6634C0532925a3b8D4C0c2f8a2a3a7b9',
                'trade_count': 150,
                'roi_30d': 25.0,
                'win_rate': 0.68,
                'name': 'Fallback Trader 1'
            },
            {
                'address': '0x8a5d7f382763a2a954e85c8d89a0e3f4a9c5f3b8',
                'trade_count': 125,
                'roi_30d': 18.5,
                'win_rate': 0.62,
                'name': 'Fallback Trader 2'
            }
        ]

    def get_leaderboard(self, page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leaderboard data with comprehensive fallback logic"""
        attempted_endpoints = []

        for _ in range(len(self.config.API_ENDPOINTS)):
            endpoint = self._get_next_endpoint()
            attempted_endpoints.append(endpoint)

            for attempt in range(self.max_retries):
                try:
                    self._respect_rate_limits()

                    params = {
                        'page': page,
                        'limit': limit,
                        'sortBy': 'roi',
                        'timeframe': '30d',
                        'testnet': str(self.config.USE_TESTNET).lower()
                    }

                    logger.info(f"📡 Requesting leaderboard from: {endpoint}")
                    logger.debug(f"Params: {params}")

                    response = self.session.get(
                        endpoint,
                        params=params,
                        timeout=self.config.API_TIMEOUT
                    )

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if isinstance(data, dict) and 'data' in data:
                                logger.info(f"✅ Success from {endpoint}: Retrieved {len(data['data'])} wallets")
                                return data['data']
                            elif isinstance(data, list):
                                logger.info(f"✅ Success from {endpoint}: Retrieved {len(data)} wallets")
                                return data
                        except Exception as e:
                            logger.error(f"JSON parse error from {endpoint}: {e}")
                            continue

                    elif response.status_code == 404:
                        logger.warning(f"404 Not Found from {endpoint} - trying next endpoint")
                        break

                    elif response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limited by {endpoint}. Waiting {retry_after}s...")
                        time.sleep(min(retry_after, 10))  # Cap wait time for demo
                        continue

                    else:
                        logger.error(f"HTTP {response.status_code} from {endpoint}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue

                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error with {endpoint}: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                except Exception as e:
                    logger.error(f"Unexpected error with {endpoint}: {str(e)}")

            logger.error(f"❌ All attempts failed for endpoint: {endpoint}")

        logger.critical(f"🚨 ALL API ENDPOINTS FAILED after trying: {attempted_endpoints}")
        fallback_wallets = self._get_fallback_wallets()
        logger.info(f"✅ Using {len(fallback_wallets)} fallback wallets")
        return fallback_wallets

def main():
    """Demo the new API endpoint system"""
    logger.info("🚀 Polymarket API Endpoint System Demo")
    logger.info("=" * 50)

    # Show configuration
    config = MockScannerConfig()
    logger.info(f"🔧 Configured {len(config.API_ENDPOINTS)} endpoints:")
    for i, endpoint in enumerate(config.API_ENDPOINTS, 1):
        logger.info(f"  {i}. {endpoint}")
    logger.info(f"📡 Testnet Mode: {config.USE_TESTNET}")
    logger.info(f"⏰ API Timeout: {config.API_TIMEOUT}s")
    logger.info(f"🔑 API Key: {'Configured' if config.POLYMARKET_API_KEY else 'Not configured'}")
    logger.info("")

    # Initialize API client
    api = PolymarketLeaderboardAPI(config)

    # Demo endpoint rotation
    logger.info("🔄 Testing endpoint rotation:")
    for i in range(6):
        endpoint = api._get_next_endpoint()
        logger.info(f"  Rotation {i+1}: {endpoint}")
    logger.info("")

    # Test API call
    logger.info("📊 Testing API call with fallback system:")
    start_time = time.time()
    results = api.get_leaderboard(page=1, limit=5)
    duration = time.time() - start_time

    logger.info("")
    logger.info("📋 Results:")
    logger.info(f"   Wallets retrieved: {len(results)}")
    logger.info(f"   Response time: {duration:.2f}s")

    if results:
        logger.info("   Sample wallets:")
        for i, wallet in enumerate(results[:3], 1):
            name = wallet.get('name', 'Unknown')
            address = wallet.get('address', 'Unknown')[:10] + '...'
            roi = wallet.get('roi_30d', 0)
            trades = wallet.get('trade_count', 0)
            logger.info(f"     {i}. {name} ({address}) - {trades} trades, {roi:.1f}% ROI")

    logger.info("")
    logger.info("✅ Demo completed successfully!")
    logger.info("🎯 The new API endpoint system provides robust fallback handling")
    logger.info("   when endpoints return 404 or other errors.")

if __name__ == "__main__":
    main()