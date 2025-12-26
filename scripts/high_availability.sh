#!/bin/bash
# High Availability Setup for Polymarket Copy Trading Bot
# Automatic failover and data synchronization between primary and standby servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SERVER_ROLE="${1:-primary}"
OPERATION="${2:-setup}"
PRIMARY_IP="${3:-192.168.1.100}"
STANDBY_IP="${4:-192.168.1.101}"
VIP="${5:-192.168.1.10}"

# HA Configuration
HA_CONFIG_DIR="/etc/polymarket-ha"
HA_LOG_DIR="/var/log/polymarket-ha"
HA_DATA_DIR="/var/lib/polymarket-ha"
RSYNC_MODULE="polymarket_data"
FLOATING_IP_SCRIPT="/usr/local/bin/manage_floating_ip.sh"

# Environment-specific configuration
case "$SERVER_ROLE" in
    primary)
        LOCAL_IP="$PRIMARY_IP"
        REMOTE_IP="$STANDBY_IP"
        SERVICE_NAME="polymarket-bot"
        BOT_USER="polymarket-bot"
        ;;
    standby)
        LOCAL_IP="$STANDBY_IP"
        REMOTE_IP="$PRIMARY_IP"
        SERVICE_NAME="polymarket-bot-standby"
        BOT_USER="polymarket-staging"  # Use staging user on standby
        ;;
    *)
        echo -e "${RED}❌ Invalid server role: $SERVER_ROLE${NC}"
        exit 1
        ;;
esac

# Logging
HA_LOG="$HA_LOG_DIR/ha_operations.log"
log_ha() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] [$SERVER_ROLE] $message" >> "$HA_LOG"

    case "$level" in
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
    esac
}

# Function to create HA directories
create_ha_directories() {
    log_ha "INFO" "Creating HA directories..."

    local dirs=("$HA_CONFIG_DIR" "$HA_LOG_DIR" "$HA_DATA_DIR")

    for dir_path in "${dirs[@]}"; do
        mkdir -p "$dir_path"
        chmod 700 "$dir_path"
    done

    log_ha "SUCCESS" "HA directories created"
}

# Function to setup SSH keys for HA communication
setup_ssh_keys() {
    log_ha "INFO" "Setting up SSH keys for HA communication..."

    local ssh_key_file="$HA_CONFIG_DIR/ha_rsa"

    # Generate SSH key if it doesn't exist
    if [ ! -f "${ssh_key_file}" ]; then
        ssh-keygen -t rsa -b 4096 -f "$ssh_key_file" -N "" -C "polymarket-ha-$SERVER_ROLE"
        chmod 600 "$ssh_key_file"
        chmod 644 "${ssh_key_file}.pub"
    fi

    # Copy public key to authorized_keys
    cat "${ssh_key_file}.pub" >> "/home/$BOT_USER/.ssh/authorized_keys"

    # Setup SSH config for easy connection
    cat >> "/home/$BOT_USER/.ssh/config" << EOF

# Polymarket HA Configuration
Host polymarket-ha-primary
    HostName $PRIMARY_IP
    User $BOT_USER
    IdentityFile $ssh_key_file
    StrictHostKeyChecking no

Host polymarket-ha-standby
    HostName $STANDBY_IP
    User $BOT_USER
    IdentityFile $ssh_key_file
    StrictHostKeyChecking no
EOF

    chown -R "$BOT_USER:$BOT_USER" "/home/$BOT_USER/.ssh"
    chmod 600 "/home/$BOT_USER/.ssh/config"

    log_ha "SUCCESS" "SSH keys configured for HA communication"
}

# Function to setup rsync for data synchronization
setup_rsync() {
    log_ha "INFO" "Setting up rsync for data synchronization..."

    # Install rsync if not present
    if ! command -v rsync >/dev/null 2>&1; then
        apt-get update && apt-get install -y rsync
    fi

    # Create rsync configuration
    cat > "/etc/rsyncd.conf" << EOF
# Polymarket HA Rsync Configuration
uid = $BOT_USER
gid = $BOT_USER
use chroot = yes
read only = no
list = no
auth users = polymarket_sync
secrets file = /etc/rsyncd.secrets
strict modes = yes

[$RSYNC_MODULE]
    path = /home/$BOT_USER/polymarket-copy-bot/data
    comment = Polymarket trading data
    read only = no
    auth users = polymarket_sync
EOF

    # Create rsync password file
    echo "polymarket_sync:CHANGE_THIS_PASSWORD_IMMEDIATELY" > "/etc/rsyncd.secrets"
    chmod 600 "/etc/rsyncd.secrets"

    # Enable and start rsync service
    systemctl enable rsync
    systemctl start rsync

    log_ha "SUCCESS" "Rsync configured for data synchronization"
}

# Function to setup floating IP management
setup_floating_ip() {
    log_ha "INFO" "Setting up floating IP management..."

    # Create floating IP management script
    cat > "$FLOATING_IP_SCRIPT" << 'EOF'
#!/bin/bash
# Floating IP Management for Polymarket HA

INTERFACE="eth0"
VIP="$1"
ACTION="$2"

case "$ACTION" in
    add)
        # Add floating IP
        ip addr add "$VIP/24" dev "$INTERFACE"
        arping -c 3 -S "$VIP" "$VIP"
        echo "Floating IP $VIP added to $INTERFACE"
        ;;
    remove)
        # Remove floating IP
        ip addr del "$VIP/24" dev "$INTERFACE"
        echo "Floating IP $VIP removed from $INTERFACE"
        ;;
    check)
        # Check if floating IP is present
        if ip addr show "$INTERFACE" | grep -q "$VIP"; then
            echo "present"
        else
            echo "absent"
        fi
        ;;
    *)
        echo "Usage: $0 <vip> <add|remove|check>"
        exit 1
        ;;
esac
EOF

    chmod 700 "$FLOATING_IP_SCRIPT"

    log_ha "SUCCESS" "Floating IP management script created"
}

# Function to setup heartbeat monitoring
setup_heartbeat() {
    log_ha "INFO" "Setting up heartbeat monitoring..."

    local heartbeat_script="/usr/local/bin/polymarket_heartbeat.sh"

    # Create heartbeat script
    cat > "$heartbeat_script" << EOF
#!/bin/bash
# Polymarket HA Heartbeat Monitor

PRIMARY_IP="$PRIMARY_IP"
STANDBY_IP="$STANDBY_IP"
HEARTBEAT_FILE="/tmp/polymarket_heartbeat"
TIMEOUT=30

# Create heartbeat file
touch "\$HEARTBEAT_FILE"
echo "\$(date +%s)" > "\$HEARTBEAT_FILE"

# Check if we're the active node (have the VIP)
if $FLOATING_IP_SCRIPT "$VIP" check | grep -q "present"; then
    # We're active, check if standby is responding
    if timeout \$TIMEOUT ssh -o ConnectTimeout=5 polymarket-ha-standby "echo 'standby_ok'" 2>/dev/null; then
        echo "standby_responding"
    else
        echo "standby_not_responding"
    fi
else
    # We're standby, check if primary is responding
    if timeout \$TIMEOUT ssh -o ConnectTimeout=5 polymarket-ha-primary "echo 'primary_ok'" 2>/dev/null; then
        echo "primary_responding"
    fi
fi
EOF

    chmod 700 "$heartbeat_script"

    log_ha "SUCCESS" "Heartbeat monitoring configured"
}

# Function to setup failover detection
setup_failover_detection() {
    log_ha "INFO" "Setting up failover detection..."

    local failover_script="/usr/local/bin/polymarket_failover.sh"

    # Create failover detection script
    cat > "$failover_script" << EOF
#!/bin/bash
# Polymarket HA Failover Detection and Execution

PRIMARY_IP="$PRIMARY_IP"
STANDBY_IP="$STANDBY_IP"
VIP="$VIP"
HEARTBEAT_TIMEOUT=60
LOG_FILE="$HA_LOG_DIR/failover.log"

log_failover() {
    echo "\$(date): \$*" >> "\$LOG_FILE"
    echo "\$*"
}

# Check if primary is responding
check_primary_health() {
    # Method 1: SSH connectivity
    if timeout 10 ssh -o ConnectTimeout=5 polymarket-ha-primary "echo 'primary_ok'" 2>/dev/null; then
        return 0
    fi

    # Method 2: Service health check via HTTP
    if curl -f --max-time 5 "http://$PRIMARY_IP:8000/health" >/dev/null 2>&1; then
        return 0
    fi

    # Method 3: Ping check
    if ping -c 3 -W 2 "$PRIMARY_IP" >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

# Check if we're the current active node
is_active_node() {
    $FLOATING_IP_SCRIPT "$VIP" check | grep -q "present"
}

# Perform failover to this node
perform_failover() {
    log_failover "INITIATING FAILOVER: Taking over from $PRIMARY_IP"

    # Stop local service if running
    systemctl stop polymarket-bot-standby 2>/dev/null || true

    # Add floating IP
    $FLOATING_IP_SCRIPT "$VIP" add

    # Start primary service
    systemctl start polymarket-bot

    # Sync data from primary (if accessible)
    if check_primary_health; then
        log_failover "Primary still accessible, syncing latest data..."
        /usr/local/bin/polymarket_sync.sh full
    fi

    # Send failover notification
    log_failover "FAILOVER COMPLETED: Now active on $VIP"

    # Send alert (implement based on your alerting system)
    echo "FAILOVER ALERT: Standby server $STANDBY_IP has taken over for failed primary $PRIMARY_IP" >&2
}

# Main failover logic
if [ "$SERVER_ROLE" = "standby" ]; then
    if ! is_active_node; then
        # We're standby, check if we should take over
        if ! check_primary_health; then
            log_failover "PRIMARY FAILURE DETECTED: $PRIMARY_IP not responding"

            # Wait a bit to avoid split-brain
            sleep 10

            # Double-check
            if ! check_primary_health; then
                perform_failover
            else
                log_failover "Primary recovered, canceling failover"
            fi
        fi
    else
        log_failover "Already active node, no failover needed"
    fi
else
    log_failover "Primary server, monitoring only"
fi
EOF

    chmod 700 "$failover_script"

    log_ha "SUCCESS" "Failover detection configured"
}

# Function to setup data synchronization
setup_data_sync() {
    log_ha "INFO" "Setting up data synchronization..."

    local sync_script="/usr/local/bin/polymarket_sync.sh"

    # Create data synchronization script
    cat > "$sync_script" << EOF
#!/bin/bash
# Polymarket HA Data Synchronization

SYNC_TYPE="\${1:-incremental}"
LOG_FILE="$HA_LOG_DIR/sync.log"

log_sync() {
    echo "\$(date): \$*" >> "\$LOG_FILE"
    echo "\$*"
}

# Full synchronization
full_sync() {
    log_sync "Starting full data synchronization..."

    # Sync data directory
    rsync -avz --delete --exclude='*.log' \
        "rsync://polymarket_sync@$REMOTE_IP/$RSYNC_MODULE/" \
        "/home/$BOT_USER/polymarket-copy-bot/data/"

    # Sync configuration (if needed)
    rsync -avz --exclude='.env*' \
        "$BOT_USER@$REMOTE_IP:/home/$BOT_USER/polymarket-copy-bot/config/" \
        "/home/$BOT_USER/polymarket-copy-bot/config/"

    log_sync "Full synchronization completed"
}

# Incremental synchronization
incremental_sync() {
    log_sync "Starting incremental data synchronization..."

    # Sync only changed files
    rsync -avz --exclude='*.log' \
        "rsync://polymarket_sync@$REMOTE_IP/$RSYNC_MODULE/" \
        "/home/$BOT_USER/polymarket-copy-bot/data/"

    log_sync "Incremental synchronization completed"
}

# Database synchronization (if using SQLite)
db_sync() {
    log_sync "Starting database synchronization..."

    # For SQLite, we need to handle WAL mode carefully
    # This is a simplified version - implement based on your DB setup

    local db_file="/home/$BOT_USER/polymarket-copy-bot/data/trade_history.db"

    # Create backup before sync
    cp "\$db_file" "\${db_file}.backup"

    # Sync database file
    rsync -avz "\$BOT_USER@$REMOTE_IP:\$db_file" "\$db_file"

    log_sync "Database synchronization completed"
}

case "\$SYNC_TYPE" in
    full)
        full_sync
        ;;
    incremental)
        incremental_sync
        ;;
    db)
        db_sync
        ;;
    *)
        echo "Usage: \$0 <full|incremental|db>"
        exit 1
        ;;
esac
EOF

    chmod 700 "$sync_script"

    log_ha "SUCCESS" "Data synchronization configured"
}

# Function to setup load balancing
setup_load_balancing() {
    log_ha "INFO" "Setting up load balancing..."

    # Install HAProxy
    apt-get install -y haproxy

    # Configure HAProxy
    cat > "/etc/haproxy/haproxy.cfg" << EOF
global
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin expose-fd listeners
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5000
    timeout client 50000
    timeout server 50000

frontend polymarket_api
    bind $VIP:80
    bind $VIP:443 ssl crt /etc/ssl/certs/polymarket.pem
    default_backend polymarket_servers

backend polymarket_servers
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200
    server primary $PRIMARY_IP:8080 check
    server standby $STANDBY_IP:8080 check backup
EOF

    # Enable HAProxy
    systemctl enable haproxy
    systemctl start haproxy

    log_ha "SUCCESS" "Load balancing configured with HAProxy"
}

# Function to setup monitoring cron jobs
setup_monitoring_cron() {
    log_ha "INFO" "Setting up monitoring cron jobs..."

    # Heartbeat monitoring (every minute)
    (crontab -u "$BOT_USER" -l 2>/dev/null; echo "* * * * * /usr/local/bin/polymarket_heartbeat.sh >> $HA_LOG_DIR/heartbeat.log 2>&1") | crontab -u "$BOT_USER" -

    # Failover check (every 30 seconds)
    (crontab -u "$BOT_USER" -l 2>/dev/null; echo "*/1 * * * * sleep 30; /usr/local/bin/polymarket_failover.sh >> $HA_LOG_DIR/failover.log 2>&1") | crontab -u "$BOT_USER" -

    # Data synchronization (every 5 minutes)
    (crontab -u "$BOT_USER" -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/polymarket_sync.sh incremental >> $HA_LOG_DIR/sync.log 2>&1") | crontab -u "$BOT_USER" -

    # Full sync (daily at 2 AM)
    (crontab -u "$BOT_USER" -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/polymarket_sync.sh full >> $HA_LOG_DIR/sync.log 2>&1") | crontab -u "$BOT_USER" -

    log_ha "SUCCESS" "Monitoring cron jobs configured"
}

# Function to test HA setup
test_ha_setup() {
    log_ha "INFO" "Testing HA setup..."

    local tests_passed=0
    local total_tests=0

    # Test SSH connectivity
    ((total_tests++))
    if ssh -o ConnectTimeout=5 -o BatchMode=yes polymarket-ha-primary "echo 'ssh_ok'" >/dev/null 2>&1; then
        ((tests_passed++))
        log_ha "SUCCESS" "SSH connectivity to primary: OK"
    else
        log_ha "ERROR" "SSH connectivity to primary: FAILED"
    fi

    # Test rsync connectivity
    ((total_tests++))
    if rsync --list-only "rsync://polymarket_sync@$REMOTE_IP/$RSYNC_MODULE/" >/dev/null 2>&1; then
        ((tests_passed++))
        log_ha "SUCCESS" "Rsync connectivity: OK"
    else
        log_ha "ERROR" "Rsync connectivity: FAILED"
    fi

    # Test floating IP management
    ((total_tests++))
    if $FLOATING_IP_SCRIPT "$VIP" check >/dev/null 2>&1; then
        ((tests_passed++))
        log_ha "SUCCESS" "Floating IP management: OK"
    else
        log_ha "ERROR" "Floating IP management: FAILED"
    fi

    # Report results
    log_ha "INFO" "HA tests completed: $tests_passed/$total_tests passed"

    if [ $tests_passed -eq $total_tests ]; then
        log_ha "SUCCESS" "All HA tests passed"
        return 0
    else
        log_ha "WARNING" "Some HA tests failed - check configuration"
        return 1
    fi
}

# Function to generate HA report
generate_ha_report() {
    log_ha "INFO" "Generating HA setup report..."

    local report_file="$HA_LOG_DIR/ha_setup_report_$(date +%Y%m%d_%H%M%S).txt"

    cat > "$report_file" << EOF
================================================================================
Polymarket Copy Trading Bot - High Availability Setup Report
Generated: $(date)
Server Role: $SERVER_ROLE
Local IP: $LOCAL_IP
Remote IP: $REMOTE_IP
================================================================================

HIGH AVAILABILITY CONFIGURATION:
- Primary Server: $PRIMARY_IP
- Standby Server: $STANDBY_IP
- Floating IP: $VIP
- Service Name: $SERVICE_NAME

SERVICES CONFIGURED:
$(systemctl list-units --type=service | grep -E "(polymarket|haproxy|rsync)" | awk '{print "- " $1 ": " $4}')

NETWORK CONFIGURATION:
- SSH Key: $HA_CONFIG_DIR/ha_rsa
- Rsync Module: $RSYNC_MODULE
- HAProxy Frontend: $VIP:80/443

DATA SYNCHRONIZATION:
- Rsync Config: /etc/rsyncd.conf
- Sync User: polymarket_sync
- Data Directory: /home/$BOT_USER/polymarket-copy-bot/data

MONITORING & FAILOVER:
- Heartbeat Script: /usr/local/bin/polymarket_heartbeat.sh
- Failover Script: /usr/local/bin/polymarket_failover.sh
- Sync Script: /usr/local/bin/polymarket_sync.sh
- Floating IP Script: $FLOATING_IP_SCRIPT

CRON JOBS CONFIGURED:
$(crontab -u "$BOT_USER" -l 2>/dev/null | grep polymarket | sed 's/^/- /')

TEST RESULTS:
$(tail -20 "$HA_LOG" | grep -E "(SUCCESS|ERROR|WARNING)" | tail -10)

CURRENT STATUS:
- Local Service: $(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "not configured")
- Remote Connectivity: $(ssh -o ConnectTimeout=3 polymarket-ha-primary "echo 'ok'" 2>/dev/null || echo "failed")
- Floating IP Status: $($FLOATING_IP_SCRIPT "$VIP" check 2>/dev/null || echo "unknown")

NEXT STEPS:
1. Update rsync password in /etc/rsyncd.secrets
2. Configure SSL certificates for HAProxy
3. Test failover scenarios
4. Configure monitoring alerts
5. Document emergency procedures

================================================================================
EOF

    chmod 600 "$report_file"

    log_ha "SUCCESS" "HA setup report generated: $report_file"
}

# Main execution
main() {
    echo -e "${PURPLE}🔄 Polymarket Copy Trading Bot - High Availability Setup${NC}"
    echo -e "${PURPLE}=========================================================${NC}"
    echo -e "${BLUE}Server Role: ${SERVER_ROLE}${NC}"
    echo -e "${BLUE}Operation: ${OPERATION}${NC}"
    echo -e "${BLUE}Primary IP: ${PRIMARY_IP}${NC}"
    echo -e "${BLUE}Standby IP: ${STANDBY_IP}${NC}"
    echo -e "${BLUE}Floating IP: ${VIP}${NC}"
    echo ""

    case "$OPERATION" in
        setup)
            create_ha_directories
            setup_ssh_keys
            setup_rsync
            setup_floating_ip
            setup_heartbeat
            setup_failover_detection
            setup_data_sync
            setup_load_balancing
            setup_monitoring_cron

            if test_ha_setup; then
                generate_ha_report
                echo -e "${GREEN}🎉 High Availability setup completed successfully!${NC}"
            else
                echo -e "${YELLOW}⚠️  HA setup completed with warnings. Check logs for details.${NC}"
            fi
            ;;
        test)
            test_ha_setup
            ;;
        failover)
            /usr/local/bin/polymarket_failover.sh
            ;;
        sync)
            /usr/local/bin/polymarket_sync.sh full
            ;;
        status)
            echo "HA Status for $SERVER_ROLE server:"
            echo "Local IP: $LOCAL_IP"
            echo "Remote IP: $REMOTE_IP"
            echo "Floating IP: $VIP"
            echo "VIP Status: $($FLOATING_IP_SCRIPT "$VIP" check)"
            echo "Local Service: $(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "not configured")"
            echo "Remote Connectivity: $(ssh -o ConnectTimeout=3 polymarket-ha-primary "echo 'ok'" 2>/dev/null || echo "failed")"
            ;;
        *)
            echo -e "${RED}❌ Invalid operation: $OPERATION${NC}"
            exit 1
            ;;
    esac
}

# Parse command line arguments
case "${1:-help}" in
    primary|standby)
        main "$@"
        ;;
    help|*)
        echo -e "${BLUE}High Availability Setup for Polymarket Copy Trading Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <server_role> <operation> [primary_ip] [standby_ip] [vip]"
        echo ""
        echo -e "${YELLOW}Server Roles:${NC}"
        echo "  primary  - Primary production server"
        echo "  standby  - Standby/failover server"
        echo ""
        echo -e "${YELLOW}Operations:${NC}"
        echo "  setup    - Complete HA setup (default)"
        echo "  test     - Test HA configuration"
        echo "  failover - Manually trigger failover"
        echo "  sync     - Synchronize data"
        echo "  status   - Show HA status"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 primary setup 192.168.1.100 192.168.1.101 192.168.1.10"
        echo "  $0 standby setup 192.168.1.100 192.168.1.101 192.168.1.10"
        echo "  $0 primary test"
        echo "  $0 standby failover"
        echo "  $0 primary status"
        echo ""
        echo -e "${YELLOW}Features:${NC}"
        echo "  • Automatic failover detection"
        echo "  • Floating IP management"
        echo "  • Data synchronization"
        echo "  • Load balancing with HAProxy"
        echo "  • Heartbeat monitoring"
        echo "  • Manual failover capability"
        exit 0
        ;;
esac
