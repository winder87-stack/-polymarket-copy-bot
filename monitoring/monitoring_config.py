"""
Monitoring Configuration System
===============================

Centralized configuration for all monitoring activities including:
- Security scanning schedules and thresholds
- Performance benchmarking parameters
- CI/CD pipeline settings
- Alert health monitoring
- Reporting and alerting configurations
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SecurityScanConfig(BaseModel):
    """Configuration for security scanning"""

    # Scan schedules
    daily_scan_enabled: bool = Field(default=True, description="Enable daily security scans")
    daily_scan_time: str = Field(default="02:00", description="Daily scan time (HH:MM)")
    weekly_deep_scan_enabled: bool = Field(
        default=True, description="Enable weekly deep security scans"
    )
    weekly_deep_scan_day: str = Field(default="sunday", description="Weekly deep scan day")

    # Scan parameters
    dependency_scan_enabled: bool = Field(
        default=True, description="Scan dependencies for vulnerabilities"
    )
    secrets_scan_enabled: bool = Field(default=True, description="Scan for exposed secrets")
    config_scan_enabled: bool = Field(default=True, description="Scan configuration security")
    code_scan_enabled: bool = Field(default=True, description="Static code security analysis")

    # Thresholds and alerts
    critical_vulnerabilities_threshold: int = Field(
        default=0, description="Alert if critical vulns > threshold"
    )
    high_vulnerabilities_threshold: int = Field(
        default=5, description="Alert if high vulns > threshold"
    )
    secrets_found_threshold: int = Field(
        default=0, description="Alert if secrets found > threshold"
    )

    # Scan tools configuration
    bandit_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_dirs": ["venv", ".git", "__pycache__", "tests"],
            "severity_threshold": "medium",
        }
    )

    safety_config: Dict[str, Any] = Field(
        default_factory=lambda: {"ignore_vulns": [], "output_format": "json"}
    )


class PerformanceBenchmarkConfig(BaseModel):
    """Configuration for performance benchmarking"""

    # Benchmark schedules
    benchmark_enabled: bool = Field(default=True, description="Enable performance benchmarking")
    benchmark_interval_hours: int = Field(default=24, description="Benchmark interval in hours")
    benchmark_duration_minutes: int = Field(default=30, description="Benchmark test duration")

    # Performance thresholds
    max_memory_mb: float = Field(default=512.0, description="Maximum allowed memory usage")
    max_cpu_percent: float = Field(default=80.0, description="Maximum allowed CPU usage")
    max_response_time_ms: float = Field(default=5000, description="Maximum response time")
    min_throughput_tps: float = Field(default=10.0, description="Minimum transactions per second")

    # Benchmark scenarios
    trade_execution_benchmark: bool = Field(default=True, description="Benchmark trade execution")
    wallet_scanning_benchmark: bool = Field(default=True, description="Benchmark wallet scanning")
    api_call_benchmark: bool = Field(default=True, description="Benchmark API calls")
    memory_usage_benchmark: bool = Field(default=True, description="Benchmark memory usage")

    # Baseline configuration
    baseline_file: str = Field(
        default="monitoring/baselines/performance_baseline.json",
        description="Performance baseline file",
    )
    baseline_update_threshold: float = Field(
        default=0.05, description="Auto-update baseline if deviation < 5%"
    )


class CICDPipelineConfig(BaseModel):
    """Configuration for CI/CD pipeline"""

    # Pipeline settings
    ci_enabled: bool = Field(default=True, description="Enable CI/CD pipeline")
    pre_commit_enabled: bool = Field(default=True, description="Enable pre-commit hooks")
    auto_merge_enabled: bool = Field(default=False, description="Enable automatic merging")

    # Test configuration
    unit_tests_enabled: bool = Field(default=True, description="Run unit tests")
    integration_tests_enabled: bool = Field(default=True, description="Run integration tests")
    performance_tests_enabled: bool = Field(default=True, description="Run performance tests")
    security_tests_enabled: bool = Field(default=True, description="Run security tests")

    # Test thresholds
    min_test_coverage: float = Field(default=85.0, description="Minimum test coverage percentage")
    max_test_duration_seconds: int = Field(default=300, description="Maximum test duration")
    allow_test_failures: bool = Field(default=False, description="Allow test failures in CI")

    # Branch protection
    protected_branches: List[str] = Field(default_factory=lambda: ["main", "master"])
    required_reviews: int = Field(default=1, description="Required reviews for PR")
    require_ci_pass: bool = Field(default=True, description="Require CI to pass")


class AlertHealthConfig(BaseModel):
    """Configuration for alert system health monitoring"""

    # Health check schedules
    health_check_enabled: bool = Field(default=True, description="Enable alert health checks")
    health_check_interval_minutes: int = Field(default=60, description="Health check interval")
    alert_test_enabled: bool = Field(default=True, description="Send test alerts periodically")

    # Health monitoring
    telegram_health_check: bool = Field(default=True, description="Monitor Telegram bot health")
    email_health_check: bool = Field(default=False, description="Monitor email alerts")
    webhook_health_check: bool = Field(default=False, description="Monitor webhook alerts")

    # Alert thresholds
    max_alert_delay_seconds: int = Field(default=300, description="Maximum acceptable alert delay")
    min_alert_success_rate: float = Field(
        default=0.95, description="Minimum alert success rate (95%)"
    )
    alert_failure_threshold: int = Field(default=3, description="Consecutive failures before alert")

    # Test configurations
    test_alert_interval_hours: int = Field(default=24, description="Test alert interval")
    test_alert_message: str = Field(
        default="🔍 Monitoring: System health check", description="Test alert message"
    )


class ReportingConfig(BaseModel):
    """Configuration for monitoring reports"""

    # Report schedules
    daily_report_enabled: bool = Field(default=True, description="Generate daily reports")
    weekly_report_enabled: bool = Field(default=True, description="Generate weekly reports")
    monthly_report_enabled: bool = Field(default=True, description="Generate monthly reports")

    # Report destinations
    telegram_reports: bool = Field(default=True, description="Send reports via Telegram")
    email_reports: bool = Field(default=False, description="Send reports via email")
    file_reports: bool = Field(default=True, description="Save reports to files")

    # Report content
    include_security_scan: bool = Field(default=True, description="Include security scan results")
    include_performance_metrics: bool = Field(
        default=True, description="Include performance metrics"
    )
    include_test_results: bool = Field(default=True, description="Include test results")
    include_alert_health: bool = Field(default=True, description="Include alert health status")

    # Report paths
    report_directory: str = Field(
        default="monitoring/reports", description="Report storage directory"
    )
    retention_days: int = Field(default=90, description="Report retention period")


class NotificationConfig(BaseModel):
    """Configuration for monitoring notifications"""

    # Notification channels
    telegram_enabled: bool = Field(default=True, description="Enable Telegram notifications")
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    slack_enabled: bool = Field(default=False, description="Enable Slack notifications")

    # Notification levels
    notify_on_critical: bool = Field(default=True, description="Notify on critical issues")
    notify_on_high: bool = Field(default=True, description="Notify on high-priority issues")
    notify_on_medium: bool = Field(default=False, description="Notify on medium-priority issues")
    notify_on_info: bool = Field(default=False, description="Notify on info-level events")

    # Escalation
    escalation_enabled: bool = Field(default=True, description="Enable notification escalation")
    escalation_delays: List[int] = Field(
        default_factory=lambda: [300, 900, 3600], description="Escalation delays in seconds"
    )


class MonitoringConfig(BaseModel):
    """Main monitoring configuration"""

    # Component configurations
    security: SecurityScanConfig = Field(default_factory=SecurityScanConfig)
    performance: PerformanceBenchmarkConfig = Field(default_factory=PerformanceBenchmarkConfig)
    ci_cd: CICDPipelineConfig = Field(default_factory=CICDPipelineConfig)
    alerts: AlertHealthConfig = Field(default_factory=AlertHealthConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    # Global settings
    monitoring_enabled: bool = Field(default=True, description="Master switch for monitoring")
    log_level: str = Field(default="INFO", description="Monitoring log level")
    timezone: str = Field(default="UTC", description="Monitoring timezone")

    # Environment-specific settings
    environment: str = Field(default="production", description="Environment (production/staging)")
    staging_mode: bool = Field(default=False, description="Enable staging-specific monitoring")

    # Paths and directories
    base_directory: str = Field(default="monitoring", description="Monitoring base directory")
    config_directory: str = Field(
        default="monitoring/config", description="Configuration directory"
    )
    logs_directory: str = Field(default="monitoring/logs", description="Logs directory")
    data_directory: str = Field(default="monitoring/data", description="Data directory")

    # Emergency settings
    emergency_mode: bool = Field(default=False, description="Enable emergency monitoring mode")
    emergency_contacts: List[str] = Field(
        default_factory=list, description="Emergency contact information"
    )

    class Config:
        arbitrary_types_allowed = True


# Global monitoring configuration instance
monitoring_config = MonitoringConfig()


# Environment variable loading
def load_from_environment():
    """Load monitoring configuration from environment variables"""
    env_mappings = {
        "monitoring.security.daily_scan_enabled": "MONITORING_SECURITY_DAILY_SCAN",
        "monitoring.performance.benchmark_enabled": "MONITORING_PERFORMANCE_ENABLED",
        "monitoring.ci_cd.ci_enabled": "MONITORING_CI_ENABLED",
        "monitoring.alerts.health_check_enabled": "MONITORING_ALERTS_ENABLED",
        "monitoring.reporting.daily_report_enabled": "MONITORING_REPORTS_ENABLED",
        "monitoring.notifications.telegram_enabled": "MONITORING_TELEGRAM_ENABLED",
    }

    for config_path, env_var in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            keys = config_path.split(".")
            current = monitoring_config
            for key in keys[:-1]:
                if not hasattr(current, key):
                    setattr(current, key, type(current)())
                current = getattr(current, key)

            final_key = keys[-1]
            if env_value.lower() in ["true", "1", "yes", "on"]:
                setattr(current, final_key, True)
            elif env_value.lower() in ["false", "0", "no", "off"]:
                setattr(current, final_key, False)
            else:
                setattr(current, final_key, env_value)


# Load environment configuration
load_from_environment()


# Create necessary directories
def ensure_directories():
    """Ensure all monitoring directories exist"""
    directories = [
        monitoring_config.base_directory,
        monitoring_config.config_directory,
        monitoring_config.logs_directory,
        monitoring_config.data_directory,
        monitoring_config.reporting.report_directory,
        "monitoring/baselines",
        "monitoring/security",
        "monitoring/performance",
        "monitoring/ci_cd",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# Ensure directories exist
ensure_directories()

if __name__ == "__main__":
    # Validation and setup
    logger.info("✅ Monitoring configuration loaded")
    logger.info(f"Environment: {monitoring_config.environment}")
    logger.info(
        f"Security scanning: {'enabled' if monitoring_config.security.daily_scan_enabled else 'disabled'}"
    )
    logger.info(
        f"Performance benchmarking: {'enabled' if monitoring_config.performance.benchmark_enabled else 'disabled'}"
    )
    logger.info(
        f"CI/CD pipeline: {'enabled' if monitoring_config.ci_cd.ci_enabled else 'disabled'}"
    )
    logger.info(
        f"Alert health monitoring: {'enabled' if monitoring_config.alerts.health_check_enabled else 'disabled'}"
    )

    print("✅ Monitoring configuration validated successfully")
