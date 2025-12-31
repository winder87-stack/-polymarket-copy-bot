Installation
============

System Requirements
-------------------

**Minimum Requirements:**

- Ubuntu 22.04 LTS or later
- Python 3.10 or later
- 2GB RAM minimum, 4GB recommended
- 10GB free disk space
- Stable internet connection

**Recommended Requirements:**

- Ubuntu 24.04 LTS
- Python 3.12
- 4GB RAM
- 20GB free disk space
- High-speed internet connection

Prerequisites
-------------

1. **Ubuntu System Setup**

   .. code-block:: bash

      # Update system packages
      sudo apt update && sudo apt upgrade -y

      # Install essential packages
      sudo apt install -y python3 python3-pip python3-venv git curl

2. **Python Environment**

   The bot requires Python 3.10 or later. Check your Python version:

   .. code-block:: bash

      python3 --version

   If you need to install Python 3.12:

   .. code-block:: bash

      # Add deadsnakes PPA
      sudo apt install -y software-properties-common
      sudo add-apt-repository ppa:deadsnakes/ppa
      sudo apt update

      # Install Python 3.12
      sudo apt install -y python3.12 python3.12-venv python3.12-pip

Installation Steps
------------------

1. **Clone the Repository**

   .. code-block:: bash

      git clone https://github.com/winder87-stack/polymarket-copy-bot.git
      cd polymarket-copy-bot

2. **Run Setup Script**

   The setup script will install all dependencies and configure the system:

   .. code-block:: bash

      sudo ./scripts/setup_ubuntu.sh

   This script will:
   - Install system dependencies
   - Set up Python virtual environment
   - Install Python packages
   - Configure systemd services
   - Set up logging directories

3. **Configure Environment**

   Copy the environment template and fill in your configuration:

   .. code-block:: bash

      cp .env.example .env
      nano .env  # Edit with your API keys and settings

   Required configuration:
   - ``PRIVATE_KEY``: Your Polygon wallet private key
   - ``POLYGONSCAN_API_KEY``: API key for transaction monitoring
   - ``CLOB_HOST``: Polymarket CLOB API endpoint
   - ``TELEGRAM_BOT_TOKEN``: For alert notifications

4. **Test Installation**

   Verify the installation by running a basic test:

   .. code-block:: bash

      # Activate virtual environment
      source venv/bin/activate

      # Test basic functionality
      python -c "from config.settings import settings; print('Configuration loaded successfully')"

      # Test CLOB connection (optional)
      python -c "from core.clob_client import PolymarketClient; client = PolymarketClient(); print('Client initialized')"

5. **Start the Bot**

   .. code-block:: bash

      # Start the service
      sudo systemctl start polymarket-bot

      # Check status
      sudo systemctl status polymarket-bot

      # View logs
      journalctl -u polymarket-bot -f

Troubleshooting Installation
----------------------------

**Common Issues:**

1. **Permission Denied**

   If you get permission errors, ensure you're running setup with sudo:

   .. code-block:: bash

      sudo ./scripts/setup_ubuntu.sh

2. **Python Version Issues**

   If the wrong Python version is being used:

   .. code-block:: bash

      # Check which python is being used
      which python3

      # Update alternatives if needed
      sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

3. **Virtual Environment Issues**

   If the virtual environment fails to create:

   .. code-block:: bash

      # Remove old venv and recreate
      rm -rf venv
      python3 -m venv venv
      source venv/bin/activate
      pip install -r requirements.txt

4. **Dependency Installation Fails**

   If pip install fails:

   .. code-block:: bash

      # Upgrade pip first
      pip install --upgrade pip

      # Install with verbose output
      pip install -r requirements.txt -v

5. **Service Won't Start**

   Check the service status and logs:

   .. code-block:: bash

      # Check service status
      sudo systemctl status polymarket-bot

      # View detailed logs
      journalctl -u polymarket-bot -n 50 --no-pager

      # Check for configuration errors
      sudo -u polymarket-bot /path/to/bot/venv/bin/python -c "from config.settings import settings; settings.validate_critical_settings()"

Next Steps
----------

After successful installation:

1. **Configure Wallets**: Add target wallet addresses in ``config/wallets.json``
2. **Set Risk Parameters**: Adjust position sizing and risk limits in ``.env``
3. **Test with Small Amounts**: Start with testnet and small positions
4. **Monitor Logs**: Regularly check logs for any issues
5. **Update Regularly**: Keep the bot updated with the latest security patches

For detailed configuration options, see the :doc:`configuration` guide.
