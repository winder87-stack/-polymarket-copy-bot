Polymarket Copy Trading Bot API Documentation
=============================================

.. image:: https://img.shields.io/badge/Python-3.12+-blue.svg
   :target: https://python.org
   :alt: Python Version

.. image:: https://img.shields.io/badge/Ubuntu-24.04-orange.svg
   :target: https://ubuntu.com
   :alt: Ubuntu Version

.. image:: https://img.shields.io/badge/License-MIT-green.svg
   :target: ../LICENSE
   :alt: License

Welcome to the comprehensive API documentation for the Polymarket Copy Trading Bot.
This documentation provides detailed information about all public interfaces,
classes, methods, and functions available in the bot's codebase.

.. warning::
   **Security Notice**: This software is for educational purposes only. Trading cryptocurrencies involves substantial risk of loss. Use at your own risk. The authors are not responsible for any losses incurred while using this software.

Overview
--------

The Polymarket Copy Trading Bot is a production-ready bot that monitors 25 hand-picked wallets on Polymarket and automatically replicates their trades. Built with security, reliability, and risk management as top priorities.

Key Features:

- **Real-time Wallet Monitoring**: Track transactions from 25+ wallets using Polygon blockchain data
- **Smart Trade Replication**: Automatically copy trades with configurable risk parameters
- **Comprehensive Risk Management**: Circuit breakers, position sizing, stop loss, and slippage protection
- **Production-Grade Infrastructure**: Systemd service integration, comprehensive logging, Telegram alerts, and health checks

Getting Started
---------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   installation
   configuration
   deployment
   troubleshooting

.. toctree::
   :maxdepth: 3
   :caption: API Reference:

   api/modules
   api/core/modules
   api/config/modules
   api/utils/modules

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide:

   contributing
   testing
   security

Core Modules
------------

The bot is organized into several core modules, each handling specific aspects of the trading system:

**Core Trading Engine** (`core/`)

- :class:`core.clob_client.PolymarketClient`: Main CLOB API client wrapper
- :class:`core.trade_executor.TradeExecutor`: Handles trade execution and position management
- :class:`core.wallet_monitor.WalletMonitor`: Monitors wallet transactions and detects trades

**Configuration Management** (`config/`)

- :class:`config.settings.Settings`: Central configuration management using Pydantic

**Utilities** (`utils/`)

- :mod:`utils.alerts`: Alert and notification management
- :mod:`utils.helpers`: Common utility functions
- :mod:`utils.security`: Security-related utilities
- :mod:`utils.logging_utils`: Enhanced logging utilities

Example Usage
-------------

Here's a basic example of how to use the Polymarket client:

.. code-block:: python

   from config.settings import settings
   from core.clob_client import PolymarketClient

   # Initialize client with default settings
   client = PolymarketClient()

   # Get current balance
   balance = await client.get_balance()
   print(f"Current USDC balance: ${balance:.2f}")

For more detailed examples, see the individual module documentation.

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. toctree::
   :hidden:

   installation
   configuration
   deployment
   troubleshooting
   contributing
   testing
   security
