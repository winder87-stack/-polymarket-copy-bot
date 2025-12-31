Configuration
=============

The Polymarket Copy Bot uses a comprehensive configuration system based on Pydantic models and environment variables. This guide covers all configuration options and best practices.

Configuration Files
-------------------

**Primary Configuration Files:**

- ``.env``: Environment variables and secrets (not committed to git)
- ``config/settings.py``: Main configuration class with validation
- ``config/wallets.json``: Target wallet addresses to monitor
- ``config/settings_staging.py``: Staging environment overrides
- ``config/wallets_staging.json``: Staging wallet configuration

Environment Variables
---------------------

**Required Variables:**

.. envvar:: PRIVATE_KEY

   Your Polygon wallet private key. **Never commit this to version control.**

   .. code-block:: bash

      PRIVATE_KEY=0x1234567890abcdef...

.. envvar:: POLYGONSCAN_API_KEY

   API key from PolygonScan for transaction monitoring.

   .. code-block:: bash

      POLYGONSCAN_API_KEY=YourApiKeyHere

.. envvar:: CLOB_HOST

   Polymarket CLOB API endpoint.

   .. code-block:: bash

      # Mainnet
      CLOB_HOST=https://clob.polymarket.com

      # Testnet
      CLOB_HOST=https://clob-testnet.polymarket.com

**Optional Variables:**

.. envvar:: TELEGRAM_BOT_TOKEN

   Telegram bot token for alert notifications.

   .. code-block:: bash

      TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

.. envvar:: TELEGRAM_CHAT_ID

   Telegram chat ID for notifications.

   .. code-block:: bash

      TELEGRAM_CHAT_ID=123456789

Trading Configuration
---------------------

**Risk Management:**

.. envvar:: MAX_POSITION_SIZE

   Maximum position size as percentage of account balance (0.01 = 1%).

   .. code-block:: bash

      MAX_POSITION_SIZE=0.05  # 5% of balance

.. envvar:: MIN_POSITION_SIZE

   Minimum position size in USDC.

   .. code-block:: bash

      MIN_POSITION_SIZE=10.0  # $10 minimum

.. envvar:: MAX_DAILY_LOSS

   Maximum daily loss limit in USDC before circuit breaker activates.

   .. code-block:: bash

      MAX_DAILY_LOSS=100.0  # $100 daily loss limit

.. envvar:: STOP_LOSS_PERCENTAGE

   Stop loss percentage (0.05 = 5%).

   .. code-block:: bash

      STOP_LOSS_PERCENTAGE=0.10  # 10% stop loss

.. envvar:: TAKE_PROFIT_PERCENTAGE

   Take profit percentage (0.10 = 10%).

   .. code-block:: bash

      TAKE_PROFIT_PERCENTAGE=0.20  # 20% take profit

**Trading Behavior:**

.. envvar:: SLIPPAGE_TOLERANCE

   Maximum slippage tolerance for orders (0.001 = 0.1%).

   .. code-block:: bash

      SLIPPAGE_TOLERANCE=0.005  # 0.5% slippage tolerance

.. envvar:: MAX_GAS_PRICE

   Maximum gas price in gwei.

   .. code-block:: bash

      MAX_GAS_PRICE=100  # 100 gwei maximum

.. envvar:: GAS_PRICE_MULTIPLIER

   Gas price multiplier for faster transactions (1.1 = 10% above market).

   .. code-block:: bash

      GAS_PRICE_MULTIPLIER=1.2  # 20% above market gas price

Monitoring Configuration
------------------------

.. envvar:: MONITOR_INTERVAL

   How often to check for new transactions (seconds).

   .. code-block:: bash

      MONITOR_INTERVAL=15  # Check every 15 seconds

.. envvar:: MAX_WALLETS_TO_MONITOR

   Maximum number of wallets to monitor simultaneously.

   .. code-block:: bash

      MAX_WALLETS_TO_MONITOR=25

.. envvar:: TRANSACTION_CACHE_SIZE

   Size of transaction cache for duplicate detection.

   .. code-block:: bash

      TRANSACTION_CACHE_SIZE=10000

.. envvar:: CACHE_CLEANUP_INTERVAL

   How often to clean up old cache entries (seconds).

   .. code-block:: bash

      CACHE_CLEANUP_INTERVAL=300  # 5 minutes

Network Configuration
---------------------

.. envvar:: POLYGON_RPC_URL

   Polygon RPC endpoint URL.

   .. code-block:: bash

      POLYGON_RPC_URL=https://polygon-rpc.com

.. envvar:: REQUEST_TIMEOUT

   HTTP request timeout in seconds.

   .. code-block:: bash

      REQUEST_TIMEOUT=30

.. envvar:: MAX_RETRIES

   Maximum number of retries for failed requests.

   .. code-block:: bash

      MAX_RETRIES=3

.. envvar:: RETRY_DELAY

   Delay between retries in seconds.

   .. code-block:: bash

      RETRY_DELAY=5

Logging Configuration
---------------------

.. envvar:: LOG_LEVEL

   Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

   .. code-block:: bash

      LOG_LEVEL=INFO

.. envvar:: LOG_MAX_SIZE

   Maximum log file size in MB.

   .. code-block:: bash

      LOG_MAX_SIZE=100  # 100MB

.. envvar:: LOG_BACKUP_COUNT

   Number of backup log files to keep.

   .. code-block:: bash

      LOG_BACKUP_COUNT=5

.. envvar:: LOG_FORMAT

   Log message format.

   .. code-block:: bash

      LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

Wallet Configuration
--------------------

The ``config/wallets.json`` file contains the list of wallets to monitor:

.. code-block:: json

   {
     "wallets": [
       {
         "address": "0x1234567890abcdef...",
         "name": "Top Trader Alpha",
         "description": "High-volume market maker",
         "enabled": true,
         "priority": 1
       },
       {
         "address": "0xabcdef1234567890...",
         "name": "Conservative Investor",
         "description": "Long-term position trader",
         "enabled": true,
         "priority": 2
       }
     ]
   }

**Wallet Fields:**

- ``address``: Wallet address to monitor (required)
- ``name``: Human-readable name (required)
- ``description``: Description of the wallet strategy
- ``enabled``: Whether to monitor this wallet
- ``priority``: Monitoring priority (lower numbers = higher priority)

Configuration Validation
------------------------

The bot validates configuration on startup:

.. code-block:: python

   from config.settings import settings

   # Validate all settings
   settings.validate_critical_settings()

   # Access specific settings
   max_loss = settings.trading.max_daily_loss
   wallets = settings.wallets.enabled_wallets

**Validation Checks:**

- Private key format and validity
- API key presence and format
- Wallet address checksums
- Risk parameter ranges
- Network connectivity
- Required file permissions

Environment-Specific Configuration
----------------------------------

**Development:**

Use ``.env.development`` with:

.. code-block:: bash

   LOG_LEVEL=DEBUG
   MONITOR_INTERVAL=60
   MAX_POSITION_SIZE=0.01

**Staging:**

Use ``.env.staging`` and ``config/settings_staging.py`` with:

.. code-block:: bash

   CLOB_HOST=https://clob-testnet.polymarket.com
   MAX_DAILY_LOSS=10.0
   MONITOR_INTERVAL=30

**Production:**

Use ``.env.production`` with conservative settings:

.. code-block:: bash

   LOG_LEVEL=WARNING
   MONITOR_INTERVAL=15
   MAX_POSITION_SIZE=0.05
   MAX_DAILY_LOSS=100.0

Configuration Best Practices
----------------------------

1. **Security First:**

   - Never commit ``.env`` files to version control
   - Use strong, unique API keys
   - Rotate keys regularly
   - Store private keys in hardware security modules when possible

2. **Risk Management:**

   - Start with conservative position sizes (0.01 = 1%)
   - Set reasonable daily loss limits
   - Test with testnet before mainnet
   - Monitor positions closely initially

3. **Performance Tuning:**

   - Adjust ``MONITOR_INTERVAL`` based on network speed
   - Balance between responsiveness and API rate limits
   - Monitor memory usage and adjust cache sizes accordingly

4. **Monitoring:**

   - Enable comprehensive logging
   - Set up alert notifications
   - Regularly review transaction logs
   - Monitor for unusual error patterns

Configuration Examples
----------------------

**Conservative Production Setup:**

.. code-block:: bash

   # Risk Management
   MAX_POSITION_SIZE=0.02
   MIN_POSITION_SIZE=5.0
   MAX_DAILY_LOSS=50.0
   STOP_LOSS_PERCENTAGE=0.15
   TAKE_PROFIT_PERCENTAGE=0.30

   # Performance
   MONITOR_INTERVAL=20
   MAX_WALLETS_TO_MONITOR=10
   MAX_GAS_PRICE=80

   # Logging
   LOG_LEVEL=INFO
   LOG_MAX_SIZE=50

**Aggressive Testnet Setup:**

.. code-block:: bash

   # Risk Management
   MAX_POSITION_SIZE=0.10
   MIN_POSITION_SIZE=1.0
   MAX_DAILY_LOSS=500.0
   STOP_LOSS_PERCENTAGE=0.50
   TAKE_PROFIT_PERCENTAGE=1.00

   # Performance
   MONITOR_INTERVAL=10
   MAX_WALLETS_TO_MONITOR=50
   MAX_GAS_PRICE=200

   # Logging
   LOG_LEVEL=DEBUG
   LOG_MAX_SIZE=100

Troubleshooting Configuration
-----------------------------

**Common Configuration Issues:**

1. **Invalid Private Key:**

   .. code-block:: text

      ERROR: Invalid private key format

   **Solution:** Ensure the private key starts with ``0x`` and is 66 characters long.

2. **Missing API Key:**

   .. code-block:: text

      ERROR: POLYGONSCAN_API_KEY not found

   **Solution:** Get an API key from https://polygonscan.com/apis and add it to ``.env``.

3. **Invalid Wallet Address:**

   .. code-block:: text

      ERROR: Invalid checksum for address: 0x...

   **Solution:** Use checksummed addresses from Etherscan/PolygonScan.

4. **Permission Denied:**

   .. code-block:: text

      ERROR: Permission denied: .env

   **Solution:** Ensure the bot user has read access to configuration files.

For more troubleshooting information, see the :doc:`troubleshooting` guide.
