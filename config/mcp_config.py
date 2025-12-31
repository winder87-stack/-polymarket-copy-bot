"""MCP Server configuration for Polymarket Copy Bot.

This module provides configuration for the codebase_search MCP server,
which enables rapid pattern-based code searching for debugging and analysis.
"""

import logging
import os
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class SearchPattern(BaseModel):
    """Configuration for a code search pattern."""

    name: str = Field(description="Pattern name for identification")
    pattern: str = Field(description="Regex pattern to search for")
    description: str = Field(description="Human-readable description of pattern")
    category: str = Field(default="general", description="Pattern category")
    severity: str = Field(
        default="info", description="Severity level: info, warning, error"
    )


class CodebaseSearchConfig(BaseModel):
    """
    Configuration for the codebase_search MCP server.

    This server provides pattern-based searching of the codebase to help
    identify critical patterns like money calculations, risk controls,
    variable conflicts, and API endpoints.

    Attributes:
        enabled: Whether the codebase search server is enabled
        cache_enabled: Enable result caching to avoid repeated scans
        cache_ttl_seconds: Time-to-live for cached results (default: 3600 = 1 hour)
        max_results: Maximum number of results to return per search
        timeout_seconds: Maximum time per search operation (default: 30s)
        rate_limit_requests_per_minute: Rate limit for searches (default: 10/min)
        allowed_directories: List of directories allowed for searching
        memory_limit_mb: Memory limit for cache in MB (default: 10MB)
        search_patterns: Dictionary of pre-defined search patterns
    """

    enabled: bool = Field(default=True, description="Enable codebase search MCP server")
    cache_enabled: bool = Field(default=True, description="Enable result caching")
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds (default: 1 hour)",
        ge=60,
        le=7200,
    )
    max_results: int = Field(
        default=1000, description="Maximum results per search", ge=10, le=10000
    )
    timeout_seconds: int = Field(
        default=30, description="Search operation timeout in seconds", ge=5, le=120
    )
    rate_limit_requests_per_minute: int = Field(
        default=10, description="Rate limit for searches", ge=1, le=60
    )
    allowed_directories: list[str] = Field(
        default_factory=list,
        description="Allowed directories for searching (empty = all project dirs)",
    )
    memory_limit_mb: float = Field(
        default=10.0, description="Memory limit for cache in MB", ge=1.0, le=100.0
    )

    # Pre-defined search patterns for critical code elements
    search_patterns: Dict[str, str] = Field(
        default_factory=lambda: {
            "money_calculations": r"(account_balance|risk_percent|position_size)\s*[\*\+\/-]",
            "risk_controls": r"circuit_breaker|is_tripped|max_position_size|max_daily_loss",
            "variable_conflicts": r"for\s+time\s+in|import\s+time",
            "api_endpoints": r"polymarket\.com/api|quicknode\.pro",
        },
        description="Pre-defined search patterns for code analysis",
    )

    # Extended pattern definitions with metadata
    extended_patterns: Dict[str, SearchPattern] = Field(
        default_factory=dict,
        description="Extended pattern definitions with metadata",
    )

    @field_validator("allowed_directories", mode="before")
    @classmethod
    def validate_allowed_directories(cls, v: any) -> list[str]:
        """
        Validate and normalize allowed directories.

        Args:
            v: Raw allowed directories value

        Returns:
            List of normalized directory paths
        """
        if not v:
            return []

        # Ensure we have a list
        if isinstance(v, str):
            directories = [v]
        elif isinstance(v, list):
            directories = list(v)
        else:
            logger.warning(f"Invalid allowed_directories type: {type(v)}")
            return []

        # Normalize paths
        normalized_dirs = []
        for directory in directories:
            directory = directory.strip()
            if directory:
                # Convert to absolute path if relative
                if not directory.startswith("/"):
                    directory = os.path.abspath(directory)
                normalized_dirs.append(directory)

        return normalized_dirs

    @model_validator(mode="after")
    def initialize_extended_patterns(self) -> "CodebaseSearchConfig":
        """
        Initialize extended patterns with metadata after model validation.

        Returns:
            Self with extended patterns initialized
        """
        pattern_descriptions = {
            "money_calculations": {
                "description": "Money/price calculation patterns",
                "category": "financial",
                "severity": "warning",
            },
            "risk_controls": {
                "description": "Risk management and circuit breaker patterns",
                "category": "risk",
                "severity": "error",
            },
            "variable_conflicts": {
                "description": "Potential variable naming conflicts (e.g., 'time')",
                "category": "code_quality",
                "severity": "warning",
            },
            "api_endpoints": {
                "description": "API endpoint URLs and RPC endpoints",
                "category": "network",
                "severity": "info",
            },
        }

        self.extended_patterns = {}
        for name, pattern in self.search_patterns.items():
            metadata = pattern_descriptions.get(name, {})
            self.extended_patterns[name] = SearchPattern(
                name=name,
                pattern=pattern,
                description=metadata.get("description", f"Pattern: {name}"),
                category=metadata.get("category", "general"),
                severity=metadata.get("severity", "info"),
            )

        return self

    def get_pattern(self, name: str) -> Optional[str]:
        """
        Get a search pattern by name.

        Args:
            name: Pattern name

        Returns:
            Pattern regex string if found, None otherwise
        """
        return self.search_patterns.get(name)

    def get_extended_pattern(self, name: str) -> Optional[SearchPattern]:
        """
        Get extended pattern metadata by name.

        Args:
            name: Pattern name

        Returns:
            SearchPattern object if found, None otherwise
        """
        return self.extended_patterns.get(name)

    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        description: str = "",
        category: str = "custom",
        severity: str = "info",
    ) -> None:
        """
        Add a custom search pattern.

        Args:
            name: Pattern name
            pattern: Regex pattern
            description: Pattern description
            category: Pattern category
            severity: Severity level
        """
        self.search_patterns[name] = pattern
        self.extended_patterns[name] = SearchPattern(
            name=name,
            pattern=pattern,
            description=description or f"Custom pattern: {name}",
            category=category,
            severity=severity,
        )
        logger.info(f"Added custom search pattern: {name}")

    def list_patterns(self) -> Dict[str, Dict[str, any]]:
        """
        List all available search patterns with metadata.

        Returns:
            Dictionary of pattern name to metadata
        """
        return {
            name: {
                "pattern": pattern.pattern,
                "description": pattern.description,
                "category": pattern.category,
                "severity": pattern.severity,
            }
            for name, pattern in self.extended_patterns.items()
        }


class MonitoringConfig(BaseModel):
    """
    Production-safe monitoring configuration for Polymarket Copy Bot.

    This MCP server prevents downtime and financial losses by detecting issues
    before they cascade, with <1% CPU overhead on trading operations.

    Key Features:
    - Zero impact on trading performance
    - Automatic issue detection and escalation
    - Resource isolation (max 100MB memory, 0.5 CPU cores)
    - Monitoring circuit breaker for extreme stress situations
    - Alert deduplication to prevent notification spam
    - Automatic recovery from monitoring crashes

    Attributes:
        enabled: Master switch for monitoring system
        dashboard_enabled: Enable real-time web dashboard
        alert_enabled: Enable alert notifications
        metrics_enabled: Enable Prometheus metrics endpoint
        memory_threshold_mb: Per-component memory limits
        api_success_threshold: API health threshold (0.0-1.0)
        api_failure_count_threshold: Consecutive failures before alert
        daily_loss_warning_percent: Warning threshold for daily losses
        daily_loss_critical_percent: Critical threshold for daily losses
        telegram_bot_token: Telegram bot for alerts
        alert_channel_id: Telegram channel ID for alerts
        alert_cooldown_minutes: Minimum time between duplicate alerts
        dashboard_refresh_seconds: Dashboard auto-refresh interval
        metrics_port: Prometheus metrics server port
        monitor_interval_seconds: Monitoring check interval
        max_cpu_percent: Maximum CPU for monitoring (default: 1%)
        max_memory_mb: Maximum memory for monitoring (default: 100MB)
        circuit_breaker_enabled: Enable monitoring circuit breaker
        recovery_enabled: Enable automatic recovery from crashes
    """

    # Main switches
    enabled: bool = Field(
        default=True, description="Enable comprehensive monitoring system"
    )
    dashboard_enabled: bool = Field(
        default=True, description="Enable real-time web dashboard"
    )
    alert_enabled: bool = Field(default=True, description="Enable alert notifications")
    metrics_enabled: bool = Field(
        default=True, description="Enable Prometheus metrics endpoint"
    )

    # Memory thresholds by component (MB)
    memory_threshold_mb: Dict[str, int] = Field(
        default_factory=lambda: {
            "wallet_monitor": 500,
            "scanner": 300,
            "trade_executor": 200,
            "total_system": 2000,
        },
        description="Memory thresholds for different components",
    )

    # API health thresholds
    api_success_threshold: float = Field(
        default=0.8, description="API success rate threshold", ge=0.0, le=1.0
    )
    api_failure_count_threshold: int = Field(
        default=5, description="Consecutive API failures before alert", ge=1, le=20
    )

    # Risk thresholds
    daily_loss_warning_percent: float = Field(
        default=0.12, description="Daily loss warning (12%)", ge=0.0, le=0.5
    )
    daily_loss_critical_percent: float = Field(
        default=0.15, description="Daily loss critical (15%)", ge=0.0, le=0.5
    )

    # Alert configuration
    telegram_bot_token: str = Field(
        default="", description="Telegram bot token for alerts"
    )
    alert_channel_id: str = Field(
        default="", description="Telegram channel ID for alerts"
    )
    alert_cooldown_minutes: int = Field(
        default=5, description="Alert cooldown (minutes)", ge=1, le=60
    )

    # Dashboard settings
    dashboard_refresh_seconds: int = Field(
        default=5, description="Dashboard refresh interval (seconds)", ge=1, le=30
    )
    dashboard_port: int = Field(
        default=8080, description="Dashboard web server port", ge=1024, le=65535
    )

    # Prometheus metrics
    metrics_port: int = Field(
        default=9090, description="Prometheus metrics port", ge=1024, le=65535
    )

    # Monitoring frequency
    monitor_interval_seconds: int = Field(
        default=30, description="Health check interval (seconds)", ge=5, le=300
    )

    # Resource limits (CRITICAL: Must not impact trading)
    max_cpu_percent: float = Field(
        default=1.0, description="Maximum CPU for monitoring (<1%)", ge=0.1, le=5.0
    )
    max_memory_mb: float = Field(
        default=100.0,
        description="Maximum memory for monitoring (MB)",
        ge=50.0,
        le=500.0,
    )

    # Safety features
    circuit_breaker_enabled: bool = Field(
        default=True, description="Enable monitoring circuit breaker"
    )
    circuit_breaker_cpu_threshold: float = Field(
        default=90.0,
        description="CPU threshold to disable monitoring",
        ge=80.0,
        le=100.0,
    )
    circuit_breaker_memory_threshold: float = Field(
        default=85.0,
        description="Memory threshold to disable monitoring",
        ge=75.0,
        le=100.0,
    )
    recovery_enabled: bool = Field(
        default=True, description="Enable automatic recovery from crashes"
    )
    recovery_interval_seconds: int = Field(
        default=60, description="Recovery check interval (seconds)", ge=30, le=300
    )
    max_recovery_attempts: int = Field(
        default=3, description="Maximum recovery attempts", ge=1, le=10
    )

    # Health check components
    check_main_bot: bool = Field(default=True, description="Check main bot health")
    check_wallet_monitor: bool = Field(
        default=True, description="Check wallet monitor health"
    )
    check_trade_executor: bool = Field(
        default=True, description="Check trade executor health"
    )
    check_circuit_breaker: bool = Field(
        default=True, description="Check circuit breaker health"
    )
    check_alert_system: bool = Field(
        default=True, description="Check alert system health"
    )

    # Alert deduplication
    deduplicate_alerts: bool = Field(
        default=True, description="Enable alert deduplication"
    )
    duplicate_alert_window_minutes: int = Field(
        default=10, description="Time window for duplicate detection", ge=5, le=30
    )

    @model_validator(mode="after")
    def validate_monitoring_config(self) -> "MonitoringConfig":
        """Validate monitoring configuration settings."""
        if self.max_cpu_percent > 1.0:
            logger.warning(
                f"⚠️ CPU limit {self.max_cpu_percent}% may impact trading. "
                "Recommended: ≤1%"
            )

        if self.max_memory_mb > 200:
            logger.warning(
                f"⚠️ Memory limit {self.max_memory_mb}MB may be excessive. "
                "Recommended: ≤100MB"
            )

        if not self.alert_enabled and self.dashboard_enabled:
            logger.info(
                "ℹ️ Dashboard enabled but alerts disabled. "
                "Issues will be visible but not sent."
            )

        # Validate risk thresholds
        if self.daily_loss_critical_percent <= self.daily_loss_warning_percent:
            logger.warning(
                "⚠️ Critical loss threshold ≤ warning threshold. Consider adjusting."
            )

        return self

    def get_component_memory_limit(self, component: str) -> int:
        """Get memory limit for a specific component."""
        return self.memory_threshold_mb.get(component, 200)


class TestingConfig(BaseModel):
    """
    Configuration for testing MCP server.

    This server provides comprehensive test execution and coverage reporting
    with real-time monitoring, automatic test generation, and integration
    with the circuit breaker system for test safety.

    Attributes:
        enabled: Whether to enable testing MCP server
        coverage_target: Minimum coverage target (default: 85%)
        run_on_commit: Run tests on commit
        run_on_pull_request: Run tests on pull request
        critical_modules: List of critical modules to test
        max_test_duration_seconds: Maximum test duration (default: 5 minutes)
        alert_on_coverage_drop: Alert when coverage drops below target
        mock_external_apis: Mock all external API calls in tests
        use_test_data: Use test data instead of production data
        max_memory_gb: Maximum memory for test runs (default: 2GB)
        max_cpu_cores: Maximum CPU cores for test runs (default: 4)
        market_hours_disable: Disable testing during market hours
    """

    enabled: bool = Field(default=True, description="Enable testing MCP server")
    coverage_target: float = Field(
        default=0.85, description="Minimum coverage target", ge=0.0, le=1.0
    )
    run_on_commit: bool = Field(default=True, description="Run tests on commit")
    run_on_pull_request: bool = Field(
        default=True, description="Run tests on pull request"
    )
    critical_modules: list[str] = Field(
        default_factory=lambda: [
            "core.trade_executor",
            "core.circuit_breaker",
            "scanners.market_analyzer",
            "core.wallet_monitor",
        ],
        description="List of critical modules to test",
    )
    max_test_duration_seconds: int = Field(
        default=300, description="Max test duration in seconds", ge=60, le=1800
    )
    alert_on_coverage_drop: bool = Field(
        default=True, description="Alert on coverage drop"
    )
    mock_external_apis: bool = Field(
        default=True, description="Mock external API calls in tests"
    )
    use_test_data: bool = Field(
        default=True, description="Use test data instead of production data"
    )
    max_memory_gb: float = Field(
        default=2.0, description="Max memory in GB for tests", ge=0.5, le=16.0
    )
    max_cpu_cores: int = Field(
        default=4, description="Max CPU cores for tests", ge=1, le=16
    )
    market_hours_disable: bool = Field(
        default=True, description="Disable testing during market hours"
    )

    @model_validator(mode="after")
    def validate_market_hours_config(self) -> "TestingConfig":
        """Validate market hours configuration."""
        if self.market_hours_disable:
            logger.info(
                "Testing will be disabled during market hours (Mon-Fri, 9:30-16:00 ET)"
            )
        return self


# Singleton instances
_monitoring_config: Optional[MonitoringConfig] = None
_testing_config: Optional[TestingConfig] = None


def get_monitoring_config() -> MonitoringConfig:
    """
    Get monitoring configuration singleton.

    Returns:
        MonitoringConfig instance
    """
    global _monitoring_config

    if _monitoring_config is None:
        # Load from environment if available
        enabled = os.getenv("MONITORING_ENABLED", "true").lower() == "true"
        dashboard_enabled = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
        alert_enabled = os.getenv("ALERT_ENABLED", "true").lower() == "true"
        metrics_enabled = os.getenv("METRICS_ENABLED", "true").lower() == "true"

        _monitoring_config = MonitoringConfig(
            enabled=enabled,
            dashboard_enabled=dashboard_enabled,
            alert_enabled=alert_enabled,
            metrics_enabled=metrics_enabled,
        )

    return _monitoring_config


def validate_monitoring_config() -> MonitoringConfig:
    """
    Validate and return monitoring configuration.

    Returns:
        Validated MonitoringConfig instance
    """
    config = get_monitoring_config()

    logger.info("✅ Monitoring configuration validated")
    logger.info(
        f"  - Enabled: {config.enabled}, Dashboard: {config.dashboard_enabled}, "
        f"Alerts: {config.alert_enabled}, Metrics: {config.metrics_enabled}"
    )
    logger.info(
        f"  - CPU limit: {config.max_cpu_percent}%, "
        f"Memory limit: {config.max_memory_mb}MB"
    )

    return config


def get_testing_config() -> TestingConfig:
    """
    Get testing configuration singleton.

    Returns:
        TestingConfig instance
    """
    global _testing_config

    if _testing_config is None:
        # Load from environment if available
        enabled = os.getenv("TESTING_SERVER_ENABLED", "true").lower() == "true"
        coverage_target = float(os.getenv("COVERAGE_TARGET", "0.85"))
        run_on_commit = os.getenv("RUN_ON_COMMIT", "true").lower() == "true"
        run_on_pull_request = os.getenv("RUN_ON_PR", "true").lower() == "true"
        alert_on_coverage_drop = (
            os.getenv("ALERT_ON_COVERAGE_DROP", "true").lower() == "true"
        )

        _testing_config = TestingConfig(
            enabled=enabled,
            coverage_target=coverage_target,
            run_on_commit=run_on_commit,
            run_on_pull_request=run_on_pull_request,
            alert_on_coverage_drop=alert_on_coverage_drop,
        )

    return _testing_config


def validate_testing_config() -> TestingConfig:
    """
    Validate and return testing configuration.

    Returns:
        Validated TestingConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    config = get_testing_config()

    logger.info("✅ Testing configuration validated")
    logger.info(
        f"  - Enabled: {config.enabled}, Coverage target: {config.coverage_target:.0%}"
    )
    logger.info(
        f"  - Critical modules: {len(config.critical_modules)}, "
        f"Max duration: {config.max_test_duration_seconds}s"
    )

    return config


# Singleton instance
_codebase_search_config: Optional[CodebaseSearchConfig] = None


def get_codebase_search_config() -> CodebaseSearchConfig:
    """
    Get the codebase search configuration singleton.

    Returns:
        CodebaseSearchConfig instance
    """
    global _codebase_search_config

    if _codebase_search_config is None:
        # Load from environment if available
        enabled = os.getenv("CODEBASE_SEARCH_ENABLED", "true").lower() == "true"
        cache_enabled = (
            os.getenv("CODEBASE_SEARCH_CACHE_ENABLED", "true").lower() == "true"
        )

        _codebase_search_config = CodebaseSearchConfig(
            enabled=enabled,
            cache_enabled=cache_enabled,
        )

    return _codebase_search_config


def validate_codebase_search_config() -> CodebaseSearchConfig:
    """
    Validate and return the codebase search configuration.

    Returns:
        Validated CodebaseSearchConfig instance

    Raises:
        ValueError: If configuration is invalid
    """
    config = get_codebase_search_config()

    # Validate allowed directories exist
    for directory in config.allowed_directories:
        if not os.path.isdir(directory):
            raise ValueError(f"Allowed directory does not exist: {directory}")

    logger.info("✅ Codebase search configuration validated")
    logger.info(f"  - Enabled: {config.enabled}, Cache: {config.cache_enabled}")
    logger.info(
        f"  - Patterns: {len(config.search_patterns)}, "
        f"Max results: {config.max_results}"
    )

    return config


if __name__ == "__main__":
    # Test configuration
    config = validate_codebase_search_config()
    print("\nAvailable search patterns:")
    for name, info in config.list_patterns().items():
        print(f"\n  {name}:")
        print(f"    Pattern: {info['pattern']}")
        print(f"    Description: {info['description']}")
        print(f"    Category: {info['category']}, Severity: {info['severity']}")
