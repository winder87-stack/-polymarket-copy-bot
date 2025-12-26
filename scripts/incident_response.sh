#!/bin/bash
# Incident Response System for Polymarket Copy Bot
# Automated incident classification, escalation, and recovery

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
INCIDENT_TYPE="${1:-auto}"
ENVIRONMENT="${2:-production}"

# Environment-specific configuration
case "$ENVIRONMENT" in
    production)
        SERVICE_NAME="polymarket-bot"
        BOT_USER="polymarket-bot"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    staging)
        SERVICE_NAME="polymarket-bot-staging"
        BOT_USER="polymarket-staging"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    development)
        SERVICE_NAME=""
        BOT_USER="${USER:-$(whoami)}"
        PROJECT_DIR="/home/$BOT_USER/polymarket-copy-bot"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

# Incident tracking
INCIDENT_ID="INC-$(date +%Y%m%d-%H%M%S)"
INCIDENT_LOG="$PROJECT_ROOT/logs/incidents.log"
INCIDENT_REPORT="$PROJECT_ROOT/logs/incident_$INCIDENT_ID.json"
INCIDENT_STATUS="investigating"

# Function to log incident events
log_incident() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$INCIDENT_ID] [$level] $message" >> "$INCIDENT_LOG"

    case "$level" in
        "CRITICAL")
            echo -e "${RED}🚨 $message${NC}"
            ;;
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

# Function to classify incident severity
classify_incident() {
    log_incident "INFO" "Classifying incident severity..."

    local severity="low"
    local impact="minimal"
    local urgency="low"

    # Check service status
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_incident "INFO" "Service is running"
    else
        severity="high"
        impact="high"
        urgency="high"
        log_incident "CRITICAL" "Service is not running"
    fi

    # Check recent errors in logs
    local error_count=$(find "$PROJECT_ROOT/logs" -name "*.log" -exec grep -c "ERROR\|CRITICAL\|FATAL" {} \; 2>/dev/null | awk '{sum += $1} END {print sum+0}')

    if [ "$error_count" -gt 100 ]; then
        severity="critical"
        impact="high"
        urgency="critical"
        log_incident "CRITICAL" "High error count detected: $error_count"
    elif [ "$error_count" -gt 10 ]; then
        severity="high"
        impact="medium"
        urgency="high"
        log_incident "ERROR" "Elevated error count: $error_count"
    fi

    # Check system resources
    local mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    local disk_usage=$(df "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')

    if [ "$mem_usage" -gt 95 ] || [ "$disk_usage" -gt 95 ]; then
        severity="critical"
        impact="high"
        urgency="critical"
        log_incident "CRITICAL" "Critical system resource usage: Memory ${mem_usage}%, Disk ${disk_usage}%"
    fi

    # Check network connectivity
    if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        severity="high"
        impact="high"
        urgency="high"
        log_incident "ERROR" "Network connectivity issues detected"
    fi

    # Set incident classification
    INCIDENT_SEVERITY="$severity"
    INCIDENT_IMPACT="$impact"
    INCIDENT_URGENCY="$urgency"

    log_incident "INFO" "Incident classified - Severity: $severity, Impact: $impact, Urgency: $urgency"
}

# Function to escalate incident based on severity
escalate_incident() {
    log_incident "INFO" "Evaluating escalation requirements..."

    case "$INCIDENT_SEVERITY" in
        "critical")
            log_incident "CRITICAL" "🚨 CRITICAL INCIDENT - Immediate escalation required"
            log_incident "CRITICAL" "Escalation Actions:"
            log_incident "CRITICAL" "  1. Alert on-call engineer immediately"
            log_incident "CRITICAL" "  2. Notify management team"
            log_incident "CRITICAL" "  3. Consider emergency rollback"
            log_incident "CRITICAL" "  4. Customer communication if affecting trading"

            # Send critical alerts
            send_critical_alerts
            ;;
        "high")
            log_incident "ERROR" "HIGH PRIORITY INCIDENT - Escalation required"
            log_incident "ERROR" "Escalation Actions:"
            log_incident "ERROR" "  1. Alert engineering team"
            log_incident "ERROR" "  2. Monitor closely for 15 minutes"
            log_incident "ERROR" "  3. Prepare rollback if needed"

            # Send high priority alerts
            send_high_priority_alerts
            ;;
        "medium")
            log_incident "WARNING" "MEDIUM PRIORITY INCIDENT - Monitor and respond"
            log_incident "WARNING" "Actions:"
            log_incident "WARNING" "  1. Log for review"
            log_incident "WARNING" "  2. Monitor for escalation"
            log_incident "WARNING" "  3. Address in next maintenance window"
            ;;
        "low")
            log_incident "INFO" "LOW PRIORITY INCIDENT - Log and monitor"
            log_incident "INFO" "Actions:"
            log_incident "INFO" "  1. Document in incident log"
            log_incident "INFO" "  2. Address in routine maintenance"
            ;;
    esac
}

# Function to activate circuit breaker
activate_circuit_breaker() {
    log_incident "WARNING" "Evaluating circuit breaker activation..."

    local should_activate=false

    # Check failure patterns
    local recent_failures=$(grep -c "CRITICAL\|FATAL" "$PROJECT_ROOT/logs"/*.log 2>/dev/null | awk '{sum += $1} END {print sum+0}')

    if [ "$recent_failures" -gt 50 ]; then
        should_activate=true
        log_incident "CRITICAL" "High failure rate detected - activating circuit breaker"
    fi

    # Check consecutive failures
    local consecutive_failures=$(tail -20 "$INCIDENT_LOG" 2>/dev/null | grep -c "CRITICAL\|FATAL" || echo "0")

    if [ "$consecutive_failures" -gt 5 ]; then
        should_activate=true
        log_incident "CRITICAL" "Consecutive failures detected - activating circuit breaker"
    fi

    if [ "$should_activate" = true ]; then
        log_incident "CRITICAL" "🔌 CIRCUIT BREAKER ACTIVATED"

        # Stop the service
        if [ -n "$SERVICE_NAME" ]; then
            systemctl stop "$SERVICE_NAME" 2>/dev/null || true
            log_incident "CRITICAL" "Service stopped due to circuit breaker"
        fi

        # Create circuit breaker flag
        touch "$PROJECT_ROOT/.circuit_breaker_active"
        echo "$(date): Circuit breaker activated due to $INCIDENT_SEVERITY incident $INCIDENT_ID" > "$PROJECT_ROOT/.circuit_breaker_active"

        # Send circuit breaker alerts
        send_circuit_breaker_alert

        INCIDENT_STATUS="circuit_breaker_activated"
    else
        log_incident "INFO" "Circuit breaker not required"
    fi
}

# Function to attempt automatic recovery
attempt_automatic_recovery() {
    log_incident "INFO" "Attempting automatic recovery..."

    # Check if circuit breaker is active
    if [ -f "$PROJECT_ROOT/.circuit_breaker_active" ]; then
        log_incident "WARNING" "Circuit breaker active - manual intervention required"
        return 1
    fi

    local recovery_attempts=0
    local max_attempts=3

    while [ $recovery_attempts -lt $max_attempts ]; do
        ((recovery_attempts++))
        log_incident "INFO" "Recovery attempt $recovery_attempts of $max_attempts"

        # Try service restart
        if [ -n "$SERVICE_NAME" ]; then
            systemctl restart "$SERVICE_NAME" 2>/dev/null

            # Wait and check
            sleep 10

            if systemctl is-active --quiet "$SERVICE_NAME"; then
                log_incident "SUCCESS" "Service recovered successfully on attempt $recovery_attempts"

                # Run health check
                if "$SCRIPT_DIR/health_monitor.sh" "$ENVIRONMENT" quick >/dev/null 2>&1; then
                    log_incident "SUCCESS" "Health check passed after recovery"
                    INCIDENT_STATUS="recovered"
                    return 0
                else
                    log_incident "WARNING" "Health check failed after recovery"
                fi
            else
                log_incident "WARNING" "Service restart failed on attempt $recovery_attempts"
            fi
        fi

        sleep 5
    done

    log_incident "ERROR" "Automatic recovery failed after $max_attempts attempts"
    return 1
}

# Function to gather incident evidence
gather_incident_evidence() {
    log_incident "INFO" "Gathering incident evidence..."

    local evidence_dir="$PROJECT_ROOT/logs/incident_evidence_$INCIDENT_ID"
    mkdir -p "$evidence_dir"

    # System information
    uname -a > "$evidence_dir/system_info.txt"
    uptime > "$evidence_dir/system_uptime.txt"
    free -h > "$evidence_dir/memory_info.txt"
    df -h > "$evidence_dir/disk_info.txt"

    # Process information
    ps aux | grep -E "(python|polymarket)" > "$evidence_dir/process_info.txt" 2>/dev/null || true

    # Recent logs
    tail -100 "$PROJECT_ROOT/logs"/*.log > "$evidence_dir/recent_logs.txt" 2>/dev/null || true

    # System logs
    journalctl -u "$SERVICE_NAME" --since "1 hour ago" > "$evidence_dir/systemd_logs.txt" 2>/dev/null || true

    # Network information
    netstat -tuln > "$evidence_dir/network_info.txt" 2>/dev/null || true

    log_incident "SUCCESS" "Incident evidence collected: $evidence_dir"
}

# Function to send critical alerts
send_critical_alerts() {
    log_incident "CRITICAL" "Sending critical incident alerts..."

    # Email alerts (if configured)
    if command -v mail >/dev/null 2>&1; then
        echo "CRITICAL INCIDENT: $INCIDENT_ID
Environment: $ENVIRONMENT
Severity: $INCIDENT_SEVERITY
Status: $INCIDENT_STATUS
Time: $(date)

Immediate action required. Check incident log: $INCIDENT_LOG
Evidence location: $PROJECT_ROOT/logs/incident_evidence_$INCIDENT_ID/" | \
        mail -s "CRITICAL: Polymarket Bot Incident $INCIDENT_ID" root 2>/dev/null || true
    fi

    # Could integrate with Slack, PagerDuty, etc. here
    log_incident "CRITICAL" "Critical alerts sent - manual verification required"
}

# Function to send high priority alerts
send_high_priority_alerts() {
    log_incident "ERROR" "Sending high priority incident alerts..."

    # Email alerts
    if command -v mail >/dev/null 2>&1; then
        echo "HIGH PRIORITY INCIDENT: $INCIDENT_ID
Environment: $ENVIRONMENT
Severity: $INCIDENT_SEVERITY
Status: $INCIDENT_STATUS
Time: $(date)

Review incident log: $INCIDENT_LOG" | \
        mail -s "HIGH PRIORITY: Polymarket Bot Incident $INCIDENT_ID" root 2>/dev/null || true
    fi
}

# Function to send circuit breaker alerts
send_circuit_breaker_alert() {
    log_incident "CRITICAL" "Sending circuit breaker activation alerts..."

    if command -v mail >/dev/null 2>&1; then
        echo "CIRCUIT BREAKER ACTIVATED: $INCIDENT_ID
Environment: $ENVIRONMENT
Service has been automatically stopped due to critical failure pattern.

Manual intervention required to restore service.
Check incident log: $INCIDENT_LOG
Circuit breaker flag: $PROJECT_ROOT/.circuit_breaker_active

To reset circuit breaker:
1. rm $PROJECT_ROOT/.circuit_breaker_active
2. systemctl start $SERVICE_NAME
3. Monitor closely for recurring issues" | \
        mail -s "CIRCUIT BREAKER: Polymarket Bot $INCIDENT_ID" root 2>/dev/null || true
    fi
}

# Function to generate incident report
generate_incident_report() {
    local timestamp=$(date -Iseconds)

    cat > "$INCIDENT_REPORT" << EOF
{
  "incident_id": "$INCIDENT_ID",
  "timestamp": "$timestamp",
  "environment": "$ENVIRONMENT",
  "severity": "$INCIDENT_SEVERITY",
  "impact": "$INCIDENT_IMPACT",
  "urgency": "$INCIDENT_URGENCY",
  "status": "$INCIDENT_STATUS",
  "classification": {
    "type": "$INCIDENT_TYPE",
    "auto_detected": true
  },
  "evidence": {
    "log_location": "$INCIDENT_LOG",
    "evidence_directory": "$PROJECT_ROOT/logs/incident_evidence_$INCIDENT_ID",
    "system_logs": "journalctl -u $SERVICE_NAME --since '1 hour ago'"
  },
  "actions_taken": [
    "incident_classification",
    "evidence_collection",
    "escalation_evaluation"
  ],
  "recommended_actions": [
    "Review incident evidence",
    "Check system logs for root cause",
    "Verify service recovery",
    "Update monitoring thresholds if needed"
  ],
  "contact_information": {
    "primary_on_call": "System Administrator",
    "backup_contact": "DevOps Team",
    "emergency_contact": "Management"
  }
}
EOF

    log_incident "SUCCESS" "Incident report generated: $INCIDENT_REPORT"
}

# Function to reset circuit breaker
reset_circuit_breaker() {
    if [ -f "$PROJECT_ROOT/.circuit_breaker_active" ]; then
        log_incident "WARNING" "Resetting circuit breaker..."

        rm -f "$PROJECT_ROOT/.circuit_breaker_active"

        # Start service with monitoring
        if [ -n "$SERVICE_NAME" ]; then
            systemctl start "$SERVICE_NAME" 2>/dev/null || log_incident "ERROR" "Failed to start service after circuit breaker reset"

            sleep 5

            if systemctl is-active --quiet "$SERVICE_NAME"; then
                log_incident "SUCCESS" "Circuit breaker reset - service started successfully"
                log_incident "WARNING" "Close monitoring recommended for next 30 minutes"
            else
                log_incident "ERROR" "Service failed to start after circuit breaker reset"
            fi
        fi
    else
        log_incident "INFO" "No active circuit breaker to reset"
    fi
}

# Main execution
main() {
    log_incident "INFO" "Starting incident response for $ENVIRONMENT environment"

    # Classify incident
    classify_incident

    # Gather evidence
    gather_incident_evidence

    # Evaluate escalation
    escalate_incident

    # Check circuit breaker
    activate_circuit_breaker

    # Attempt automatic recovery (unless circuit breaker active)
    if [ "$INCIDENT_STATUS" != "circuit_breaker_activated" ]; then
        if attempt_automatic_recovery; then
            log_incident "SUCCESS" "Incident resolved through automatic recovery"
        else
            log_incident "WARNING" "Automatic recovery failed - manual intervention required"
        fi
    fi

    # Generate report
    generate_incident_report

    # Final status
    echo ""
    echo -e "${RED}🚨 INCIDENT RESPONSE COMPLETED${NC}"
    echo -e "${BLUE}📋 Incident ID: $INCIDENT_ID${NC}"
    echo -e "${BLUE}📊 Severity: $INCIDENT_SEVERITY${NC}"
    echo -e "${BLUE}📈 Status: $INCIDENT_STATUS${NC}"
    echo -e "${BLUE}📄 Report: $INCIDENT_REPORT${NC}"
    echo -e "${BLUE}📁 Evidence: $PROJECT_ROOT/logs/incident_evidence_$INCIDENT_ID/${NC}"

    if [ "$INCIDENT_SEVERITY" = "critical" ] || [ "$INCIDENT_STATUS" = "circuit_breaker_activated" ]; then
        echo -e "${RED}⚠️  IMMEDIATE ATTENTION REQUIRED${NC}"
    fi

    log_incident "INFO" "Incident response completed"
}

# Parse command line arguments
case "${1:-help}" in
    auto|manual)
        main "$@"
        ;;
    classify)
        classify_incident
        ;;
    escalate)
        escalate_incident
        ;;
    circuit-breaker-reset)
        reset_circuit_breaker
        ;;
    evidence)
        gather_incident_evidence
        ;;
    help|*)
        echo -e "${BLUE}Incident Response System for Polymarket Copy Bot${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  $0 <incident_type> [environment]"
        echo ""
        echo -e "${YELLOW}Incident Types:${NC}"
        echo "  auto                 - Automatic incident detection and response"
        echo "  manual               - Manual incident declaration"
        echo "  classify             - Classify current incident severity"
        echo "  escalate             - Evaluate escalation requirements"
        echo "  circuit-breaker-reset - Reset active circuit breaker"
        echo "  evidence             - Gather incident evidence only"
        echo ""
        echo -e "${YELLOW}Environments:${NC}"
        echo "  production  - Production environment (default)"
        echo "  staging     - Staging environment"
        echo "  development - Development environment"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  $0 auto production"
        echo "  $0 circuit-breaker-reset staging"
        echo "  $0 evidence"
        echo ""
        echo -e "${YELLOW}Circuit Breaker:${NC}"
        echo "  Automatically stops service on critical failure patterns"
        echo "  Manual reset required after issue resolution"
        echo "  Flag file: \$PROJECT_DIR/.circuit_breaker_active"
        echo ""
        echo -e "${YELLOW}Severity Levels:${NC}"
        echo "  critical - Service down, data loss, immediate action"
        echo "  high     - Service degraded, urgent response"
        echo "  medium   - Performance issues, monitor closely"
        echo "  low      - Minor issues, routine handling"
        exit 0
        ;;
esac
