#!/bin/bash
# Setup cron job for weekly API endpoint discovery

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create log directory
sudo mkdir -p /var/log/polymarket-bot

# Create logrotate configuration
sudo tee /etc/logrotate.d/polymarket-api-discovery > /dev/null << EOF
/var/log/polymarket-bot/api_discovery.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    create 0644 polymarket polymarket
    postrotate
        systemctl reload polymarket-api-discovery.service || true
    endscript
}
EOF

# Create systemd service for API discovery
sudo tee /etc/systemd/system/polymarket-api-discovery.service > /dev/null << EOF
[Unit]
Description=Polymarket API Endpoint Discovery
After=network.target

[Service]
Type=oneshot
User=polymarket
Group=polymarket
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/scripts/discover_api_endpoints.py
StandardOutput=append:/var/log/polymarket-bot/api_discovery.log
StandardError=append:/var/log/polymarket-bot/api_discovery.log
Environment=PYTHONPATH=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer for weekly execution
sudo tee /etc/systemd/system/polymarket-api-discovery.timer > /dev/null << EOF
[Unit]
Description=Run Polymarket API discovery weekly
Requires=polymarket-api-discovery.service

[Timer]
OnCalendar=weekly
Persistent=true
Unit=polymarket-api-discovery.service

[Install]
WantedBy=timers.target
EOF

# Reload systemd and enable timer
sudo systemctl daemon-reload
sudo systemctl enable polymarket-api-discovery.timer
sudo systemctl start polymarket-api-discovery.timer

echo "✅ API discovery cron job setup complete!"
echo "📅 Runs weekly on Sundays at 00:00"
echo "📊 Logs: /var/log/polymarket-bot/api_discovery.log"
echo ""
echo "To run manually:"
echo "sudo systemctl start polymarket-api-discovery.service"
echo ""
echo "To check status:"
echo "sudo systemctl status polymarket-api-discovery.timer"
echo "sudo systemctl list-timers | grep polymarket"
