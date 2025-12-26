#!/bin/bash
# Incident Severity Assessment Script
# ===================================
#
# Quickly assesses the severity of current incidents
# to determine appropriate response procedures.
#
# Usage: ./scripts/assess_incident_severity.sh
#
# Output: Incident severity level and recommended actions

set -e

echo "🚨 INCIDENT SEVERITY ASSESSMENT"
echo "==============================="

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

# Assessment variables
SEVERITY="UNKNOWN"
IMPACT_LEVEL="UNKNOWN"
RESPONSE_TIME="UNKNOWN"
ACTIONS=()

# Function to check service status
check_service_status() {
    if systemctl is-active --quiet polymarket-bot 2>/dev/null; then
        echo -e "${GREEN}✅ Service is running${NC}"
        return 0
    else
        echo -e "${RED}❌ Service is NOT running${NC}"
        return 1
    fi
}

# Function to check recent errors
check_recent_errors() {
    local error_count=0

    # Check systemd logs for errors in last 5 minutes
    if command -v journalctl >/dev/null 2>&1; then
        error_count=$(journalctl -u polymarket-bot --since "5 minutes ago" -q | grep -c -E "(ERROR|CRITICAL|FATAL)" || true)
    fi

    # Check application logs for errors
    if [ -f "logs/polymarket_bot.log" ]; then
        local log_errors=$(tail -n 100 logs/polymarket_bot.log | grep -c -E "(ERROR|CRITICAL|FATAL)" || true)
        error_count=$((error_count + log_errors))
    fi

    echo "Recent errors (last 5 min): $error_count"

    if [ "$error_count" -gt 10 ]; then
        echo -e "${RED}🚨 High error rate detected${NC}"
        return 2
    elif [ "$error_count" -gt 0 ]; then
        echo -e "${YELLOW}⚠️ Some errors detected${NC}"
        return 1
    else
        echo -e "${GREEN}✅ No recent errors${NC}"
        return 0
    fi
}

# Function to check financial impact
check_financial_impact() {
    # This is a placeholder - in real implementation, you'd check:
    # - Recent P&L
    # - Open positions
    # - Failed trades
    # - Wallet balance changes

    echo "Financial impact assessment: PLACEHOLDER"
    echo "  - Recent P&L: Check manually"
    echo "  - Open positions: Check manually"
    echo "  - Failed trades: Check manually"

    # For now, assume no immediate financial impact
    return 0
}

# Function to check system resources
check_system_resources() {
    # Check memory usage
    local mem_percent=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')

    # Check disk usage
    local disk_percent=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

    # Check CPU load
    local load_avg=$(uptime | awk -F'load average:' '{ print $2 }' | cut -d, -f1 | tr -d ' ')

    echo "System resources:"
    echo "  Memory usage: ${mem_percent}%"
    echo "  Disk usage: ${disk_percent}%"
    echo "  Load average: ${load_avg}"

    # Assess resource issues
    local resource_issues=0

    if [ "$mem_percent" -gt 90 ]; then
        echo -e "${RED}🚨 Critical memory usage${NC}"
        resource_issues=$((resource_issues + 1))
    elif [ "$mem_percent" -gt 75 ]; then
        echo -e "${YELLOW}⚠️ High memory usage${NC}"
        resource_issues=$((resource_issues + 1))
    fi

    if [ "$disk_percent" -gt 95 ]; then
        echo -e "${RED}🚨 Critical disk usage${NC}"
        resource_issues=$((resource_issues + 1))
    elif [ "$disk_percent" -gt 85 ]; then
        echo -e "${YELLOW}⚠️ High disk usage${NC}"
        resource_issues=$((resource_issues + 1))
    fi

    return $resource_issues
}

# Function to assess overall impact
assess_overall_impact() {
    local service_down=0
    local error_severity=0
    local financial_impact=0
    local resource_issues=0

    echo ""
    echo "🔍 ASSESSING OVERALL IMPACT"
    echo "==========================="

    # Check service status
    if ! check_service_status; then
        service_down=1
        echo "  - Service is down"
    fi

    # Check errors
    check_recent_errors
    error_severity=$?

    # Check financial impact
    check_financial_impact
    financial_impact=$?

    # Check resources
    check_system_resources
    resource_issues=$?

    echo ""
    echo "📊 IMPACT SUMMARY"
    echo "================="
    echo "Service down: $service_down"
    echo "Error severity: $error_severity"
    echo "Financial impact: $financial_impact"
    echo "Resource issues: $resource_issues"

    # Determine severity
    local total_score=$((service_down * 3 + error_severity * 2 + financial_impact * 2 + resource_issues))

    if [ $total_score -ge 8 ]; then
        SEVERITY="CRITICAL"
        IMPACT_LEVEL="System Down / Data Loss / Financial Loss"
        RESPONSE_TIME="< 5 minutes"
        ACTIONS=(
            "🔔 Alert all emergency contacts immediately"
            "⏹️ Stop all trading operations"
            "🔄 Initiate rollback procedures"
            "📞 Call emergency bridge line"
            "📋 Create incident ticket"
        )
    elif [ $total_score -ge 5 ]; then
        SEVERITY="HIGH"
        IMPACT_LEVEL="Degraded Performance / Partial Failure"
        RESPONSE_TIME="< 30 minutes"
        ACTIONS=(
            "🔔 Alert incident response team"
            "🔍 Begin investigation"
            "📊 Monitor system closely"
            "⚡ Implement temporary mitigations"
            "📋 Document incident details"
        )
    elif [ $total_score -ge 2 ]; then
        SEVERITY="MEDIUM"
        IMPACT_LEVEL="Minor Issues / Warnings"
        RESPONSE_TIME="< 4 hours"
        ACTIONS=(
            "🔔 Notify on-call engineer"
            "🔍 Investigate root cause"
            "📊 Monitor for escalation"
            "🔧 Apply fixes during next maintenance window"
            "📋 Log incident for review"
        )
    else
        SEVERITY="LOW"
        IMPACT_LEVEL="Monitoring Alerts / Routine Issues"
        RESPONSE_TIME="Next business day"
        ACTIONS=(
            "📋 Log incident details"
            "🔍 Review during regular maintenance"
            "📊 Add to monitoring dashboard"
            "🔧 Plan fixes for next deployment"
        )
    fi
}

# Main assessment
echo "Starting incident severity assessment..."
echo ""

assess_overall_impact

echo ""
echo "🚨 INCIDENT SEVERITY: $SEVERITY"
echo "📊 Impact Level: $IMPACT_LEVEL"
echo "⏰ Required Response Time: $RESPONSE_TIME"
echo ""

echo "🎯 RECOMMENDED ACTIONS:"
echo "======================"
for i in "${!ACTIONS[@]}"; do
    echo "$((i+1)). ${ACTIONS[$i]}"
done

echo ""
echo "📞 EMERGENCY CONTACTS:"
echo "======================"

# Display emergency contacts (customize as needed)
echo "Development Lead: [Name] - [Phone] - [Email]"
echo "Operations Lead: [Name] - [Phone] - [Email]"
echo "Security Lead: [Name] - [Phone] - [Email]"
echo ""
echo "Emergency Bridge: [Bridge Line Number]"
echo ""

echo "📋 INCIDENT LOGGING:"
echo "==================="
echo "Incident ID: $(date +%Y%m%d_%H%M%S)"
echo "Assessment Time: $(date)"
echo "Assessed By: $(whoami)"
echo "Severity: $SEVERITY"
echo ""

# Color coding for severity
case $SEVERITY in
    "CRITICAL")
        echo -e "${RED}🔴 CRITICAL INCIDENT - IMMEDIATE ACTION REQUIRED${NC}"
        ;;
    "HIGH")
        echo -e "${RED}🟠 HIGH PRIORITY INCIDENT - URGENT RESPONSE${NC}"
        ;;
    "MEDIUM")
        echo -e "${YELLOW}🟡 MEDIUM PRIORITY INCIDENT - RESPOND WITHIN HOURS${NC}"
        ;;
    "LOW")
        echo -e "${GREEN}🟢 LOW PRIORITY INCIDENT - ROUTINE HANDLING${NC}"
        ;;
    *)
        echo -e "${BLUE}❓ UNKNOWN SEVERITY - MANUAL ASSESSMENT REQUIRED${NC}"
        ;;
esac

echo ""
echo "💡 Next Steps:"
echo "1. Acknowledge incident: Reply 'INCIDENT ACKNOWLEDGED - Investigating'"
echo "2. Follow recommended actions above"
echo "3. Update incident response team via appropriate channels"
echo "4. Begin detailed investigation and documentation"
echo ""

# Exit with severity code
case $SEVERITY in
    "CRITICAL")
        exit 2
        ;;
    "HIGH")
        exit 1
        ;;
    "MEDIUM")
        exit 1
        ;;
    "LOW")
        exit 0
        ;;
    *)
        exit 3  # Unknown
        ;;
esac
