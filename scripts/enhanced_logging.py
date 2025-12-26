#!/usr/bin/env python3
"""
Enhanced Logging System for Polymarket Copy Bot

Provides advanced logging capabilities including:
- Structured JSON logging with correlation IDs
- Runtime log level management
- Log anomaly detection and alerting
- Log aggregation and analysis
- Performance-aware logging
"""

import os
import sys
import json
import time
import uuid
import threading
import logging
import logging.handlers
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import hashlib
import re

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CorrelationContext:
    """Context manager for correlation IDs"""

    _current_context = threading.local()

    def __init__(self, correlation_id: Optional[str] = None, parent_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.parent_id = parent_id

    def __enter__(self):
        self._previous_context = getattr(self._current_context, 'correlation_id', None)
        self._current_context.correlation_id = self.correlation_id
        self._current_context.parent_id = self.parent_id
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._current_context.correlation_id = self._previous_context

    @classmethod
    def get_current_correlation_id(cls) -> Optional[str]:
        """Get current correlation ID"""
        return getattr(cls._current_context, 'correlation_id', None)

    @classmethod
    def get_current_parent_id(cls) -> Optional[str]:
        """Get current parent ID"""
        return getattr(cls._current_context, 'parent_id', None)

class StructuredLogger(logging.Logger):
    """Enhanced logger with structured logging capabilities"""

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        self._correlation_filter = CorrelationFilter()

    def _log(self, level: int, msg: object, args, exc_info=None, extra=None, stack_info=False, stacklevel=1) -> None:
        """Override _log to add structured logging"""
        if extra is None:
            extra = {}

        # Add correlation IDs
        correlation_id = CorrelationContext.get_current_correlation_id()
        if correlation_id:
            extra['correlation_id'] = correlation_id

        parent_id = CorrelationContext.get_current_parent_id()
        if parent_id:
            extra['parent_id'] = parent_id

        # Add performance metrics
        extra['timestamp'] = datetime.now().isoformat()
        extra['thread_id'] = threading.get_ident()
        extra['process_id'] = os.getpid()

        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)

class CorrelationFilter(logging.Filter):
    """Filter to add correlation IDs to log records"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = CorrelationContext.get_current_correlation_id()
        if not hasattr(record, 'parent_id'):
            record.parent_id = CorrelationContext.get_current_parent_id()
        return True

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if self.include_extra and hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                             'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                             'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                             'thread', 'threadName', 'processName', 'process', 'message']:
                    if isinstance(value, (str, int, float, bool, type(None))):
                        log_entry[key] = value
                    elif isinstance(value, (list, dict)):
                        log_entry[key] = value
                    else:
                        log_entry[key] = str(value)

        return json.dumps(log_entry, default=str)

class PerformanceFormatter(logging.Formatter):
    """Performance-aware formatter that truncates long messages"""

    def __init__(self, max_message_length: int = 1000):
        super().__init__()
        self.max_message_length = max_message_length

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if len(message) > self.max_message_length:
            message = message[:self.max_message_length] + "..."
            record.msg = message

        return super().format(record)

class LogAnomalyDetector:
    """Detects anomalies in log patterns"""

    def __init__(self, window_minutes: int = 5, alert_threshold: int = 10):
        self.window_minutes = window_minutes
        self.alert_threshold = alert_threshold
        self.log_entries: List[Dict[str, Any]] = []
        self.anomaly_patterns = {
            'error_burst': re.compile(r'ERROR|FATAL|CRITICAL'),
            'repeated_failures': re.compile(r'failed|error|exception'),
            'performance_degradation': re.compile(r'latency|timeout|slow'),
            'security_events': re.compile(r'unauthorized|denied|breach|attack')
        }

    def add_log_entry(self, log_entry: Dict[str, Any]) -> None:
        """Add log entry for analysis"""
        self.log_entries.append(log_entry)

        # Clean old entries
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        self.log_entries = [
            entry for entry in self.log_entries
            if datetime.fromisoformat(entry.get('timestamp', '2000-01-01T00:00:00')) > cutoff_time
        ]

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in recent logs"""
        anomalies = []

        if len(self.log_entries) < 5:
            return anomalies

        # Analyze patterns
        error_count = sum(1 for entry in self.log_entries
                         if self.anomaly_patterns['error_burst'].search(entry.get('message', '')))

        failure_count = sum(1 for entry in self.log_entries
                           if self.anomaly_patterns['repeated_failures'].search(entry.get('message', '')))

        perf_count = sum(1 for entry in self.log_entries
                        if self.anomaly_patterns['performance_degradation'].search(entry.get('message', '')))

        security_count = sum(1 for entry in self.log_entries
                            if self.anomaly_patterns['security_events'].search(entry.get('message', '')))

        # Check thresholds
        if error_count >= self.alert_threshold:
            anomalies.append({
                "type": "error_burst",
                "severity": "high",
                "count": error_count,
                "description": f"High error rate: {error_count} errors in {self.window_minutes} minutes"
            })

        if failure_count >= self.alert_threshold * 2:
            anomalies.append({
                "type": "repeated_failures",
                "severity": "medium",
                "count": failure_count,
                "description": f"Repeated failures: {failure_count} failure messages"
            })

        if perf_count >= self.alert_threshold:
            anomalies.append({
                "type": "performance_degradation",
                "severity": "medium",
                "count": perf_count,
                "description": f"Performance issues: {perf_count} performance-related messages"
            })

        if security_count > 0:
            anomalies.append({
                "type": "security_events",
                "severity": "critical",
                "count": security_count,
                "description": f"Security events detected: {security_count} security-related messages"
            })

        return anomalies

class RuntimeLogManager:
    """Manages log levels at runtime"""

    def __init__(self):
        self.loggers: Dict[str, logging.Logger] = {}
        self._lock = threading.Lock()

    def register_logger(self, name: str, logger: logging.Logger) -> None:
        """Register a logger for management"""
        with self._lock:
            self.loggers[name] = logger

    def set_log_level(self, logger_name: str, level: str) -> bool:
        """Set log level for a specific logger"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        if level not in level_map:
            return False

        with self._lock:
            if logger_name in self.loggers:
                self.loggers[logger_name].setLevel(level_map[level])
                logger.info(f"Changed log level for {logger_name} to {level}")
                return True

        return False

    def set_global_log_level(self, level: str) -> None:
        """Set log level for all registered loggers"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        if level in level_map:
            with self._lock:
                for logger in self.loggers.values():
                    logger.setLevel(level_map[level])
                logger.info(f"Changed global log level to {level}")

    def get_registered_loggers(self) -> List[str]:
        """Get list of registered logger names"""
        with self._lock:
            return list(self.loggers.keys())

class EnhancedLoggingSystem:
    """Complete enhanced logging system"""

    def __init__(self, project_root: Optional[Path] = None, log_level: str = "INFO"):
        self.project_root = project_root or Path(__file__).parent.parent
        self.log_dir = self.project_root / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # Initialize components
        self.runtime_manager = RuntimeLogManager()
        self.anomaly_detector = LogAnomalyDetector()

        # Setup loggers
        self._setup_loggers(log_level)

        # Anomaly detection thread
        self.anomaly_thread: Optional[threading.Thread] = None
        self.anomaly_active = False

    def _setup_loggers(self, log_level: str) -> None:
        """Setup all loggers with appropriate handlers"""

        # Convert string level to logging level
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        numeric_level = level_map.get(log_level.upper(), logging.INFO)

        # Main application logger
        self.app_logger = self._create_structured_logger(
            'polymarket.app',
            numeric_level,
            'app.log',
            use_json=True
        )

        # Trade logger
        self.trade_logger = self._create_structured_logger(
            'polymarket.trade',
            numeric_level,
            'trade.log',
            use_json=True
        )

        # System logger
        self.system_logger = self._create_structured_logger(
            'polymarket.system',
            numeric_level,
            'system.log',
            use_json=False
        )

        # Security logger
        self.security_logger = self._create_structured_logger(
            'polymarket.security',
            logging.WARNING,  # Always log security events
            'security.log',
            use_json=True
        )

        # Performance logger
        self.performance_logger = self._create_structured_logger(
            'polymarket.performance',
            numeric_level,
            'performance.log',
            use_json=True
        )

        # Error logger (separate for critical errors)
        self.error_logger = self._create_structured_logger(
            'polymarket.error',
            logging.ERROR,
            'errors.log',
            use_json=True
        )

    def _create_structured_logger(self, name: str, level: int, filename: str,
                                use_json: bool = True, max_bytes: int = 10*1024*1024,
                                backup_count: int = 5) -> StructuredLogger:
        """Create a structured logger with appropriate handlers"""

        # Create logger
        structured_logger = StructuredLogger(name, level)

        # Add correlation filter
        structured_logger.addFilter(CorrelationFilter())

        # Create rotating file handler
        log_file = self.log_dir / filename
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )

        # Set formatter
        if use_json:
            formatter = JSONFormatter()
        else:
            formatter = PerformanceFormatter()

        file_handler.setFormatter(formatter)
        structured_logger.addHandler(file_handler)

        # Register with runtime manager
        self.runtime_manager.register_logger(name, structured_logger)

        return structured_logger

    def start_anomaly_detection(self) -> None:
        """Start anomaly detection monitoring"""
        if self.anomaly_active:
            return

        self.anomaly_active = True
        self.anomaly_thread = threading.Thread(target=self._anomaly_detection_loop, daemon=True)
        self.anomaly_thread.start()

    def stop_anomaly_detection(self) -> None:
        """Stop anomaly detection"""
        self.anomaly_active = False
        if self.anomaly_thread:
            self.anomaly_thread.join(timeout=5.0)

    def _anomaly_detection_loop(self) -> None:
        """Monitor logs for anomalies"""
        while self.anomaly_active:
            try:
                # Read recent log entries from all log files
                for log_file in self.log_dir.glob("*.log"):
                    try:
                        with open(log_file, 'r') as f:
                            # Read last few lines
                            lines = f.readlines()[-10:]
                            for line in lines:
                                try:
                                    if line.strip().startswith('{'):
                                        log_entry = json.loads(line.strip())
                                        self.anomaly_detector.add_log_entry(log_entry)
                                except json.JSONDecodeError:
                                    # Not JSON, skip
                                    continue
                    except Exception as e:
                        logger.error(f"Error reading log file {log_file}: {e}")

                # Check for anomalies
                anomalies = self.anomaly_detector.detect_anomalies()
                for anomaly in anomalies:
                    self.app_logger.warning(
                        f"ANOMALY DETECTED: {anomaly['description']}",
                        extra={
                            'anomaly_type': anomaly['type'],
                            'anomaly_severity': anomaly['severity'],
                            'anomaly_count': anomaly['count']
                        }
                    )

            except Exception as e:
                logger.error(f"Anomaly detection error: {e}")

            time.sleep(60)  # Check every minute

    def get_log_statistics(self) -> Dict[str, Any]:
        """Get statistics about log files"""
        stats = {}

        for log_file in self.log_dir.glob("*.log*"):
            try:
                stat_info = log_file.stat()
                base_name = log_file.name.split('.')[0]

                if base_name not in stats:
                    stats[base_name] = {
                        'total_size': 0,
                        'file_count': 0,
                        'last_modified': None
                    }

                stats[base_name]['total_size'] += stat_info.st_size
                stats[base_name]['file_count'] += 1

                if stats[base_name]['last_modified'] is None or stat_info.st_mtime > stats[base_name]['last_modified']:
                    stats[base_name]['last_modified'] = stat_info.st_mtime

            except Exception as e:
                logger.error(f"Error getting stats for {log_file}: {e}")

        # Convert timestamps
        for logger_stats in stats.values():
            if logger_stats['last_modified']:
                logger_stats['last_modified'] = datetime.fromtimestamp(logger_stats['last_modified']).isoformat()

        return stats

    def search_logs(self, query: str, logger_name: Optional[str] = None,
                   hours: int = 24, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search logs with various filters"""
        results = []
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Determine which log files to search
        if logger_name:
            log_files = [self.log_dir / f"{logger_name}.log"]
        else:
            log_files = list(self.log_dir.glob("*.log"))

        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            if line.strip().startswith('{'):
                                log_entry = json.loads(line.strip())
                                entry_time = datetime.fromisoformat(log_entry.get('timestamp', '2000-01-01T00:00:00'))

                                # Apply filters
                                if entry_time < cutoff_time:
                                    continue

                                if level and log_entry.get('level') != level:
                                    continue

                                if query.lower() not in json.dumps(log_entry).lower():
                                    continue

                                results.append(log_entry)

                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                logger.error(f"Error searching log file {log_file}: {e}")

        # Sort by timestamp (most recent first)
        results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return results

    def export_logs(self, filename: str, hours: int = 24,
                   logger_name: Optional[str] = None) -> str:
        """Export logs to a compressed file"""
        import gzip

        export_file = self.log_dir / f"{filename}.gz"
        search_results = self.search_logs("", logger_name, hours)

        with gzip.open(export_file, 'wt', encoding='utf-8') as f:
            for entry in search_results:
                f.write(json.dumps(entry) + '\n')

        return str(export_file)

# Global logging system instance
logging_system = None

def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    global logging_system
    if logging_system is None:
        logging_system = EnhancedLoggingSystem()

    # Return appropriate logger based on name
    if 'trade' in name.lower():
        return logging_system.trade_logger
    elif 'security' in name.lower():
        return logging_system.security_logger
    elif 'performance' in name.lower():
        return logging_system.performance_logger
    elif 'error' in name.lower():
        return logging_system.error_logger
    elif 'system' in name.lower():
        return logging_system.system_logger
    else:
        return logging_system.app_logger

def setup_enhanced_logging(log_level: str = "INFO") -> EnhancedLoggingSystem:
    """Setup the enhanced logging system"""
    global logging_system
    logging_system = EnhancedLoggingSystem(log_level=log_level)
    logging_system.start_anomaly_detection()
    return logging_system

def main():
    """CLI interface for enhanced logging system"""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Logging System for Polymarket Copy Bot")
    parser.add_argument("action", choices=[
        "setup", "stats", "search", "export", "set-level", "anomalies"
    ])
    parser.add_argument("--level", help="Log level for setup")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--logger", help="Logger name")
    parser.add_argument("--hours", type=int, default=24, help="Hours to search/export")
    parser.add_argument("--filename", help="Export filename")
    parser.add_argument("--new-level", help="New log level")

    args = parser.parse_args()

    if args.action == "setup":
        level = args.level or "INFO"
        logging_sys = setup_enhanced_logging(level)
        print(f"✅ Enhanced logging system setup with level {level}")

    elif args.action == "stats":
        if not logging_system:
            print("❌ Logging system not initialized. Run 'setup' first.")
            sys.exit(1)

        stats = logging_system.get_log_statistics()
        print("📊 Log Statistics:")
        for logger_name, logger_stats in stats.items():
            size_mb = logger_stats['total_size'] / (1024 * 1024)
            print(f"  {logger_name}: {size_mb:.1f}MB in {logger_stats['file_count']} files")
            if logger_stats['last_modified']:
                print(f"    Last modified: {logger_stats['last_modified']}")

    elif args.action == "search":
        if not logging_system:
            print("❌ Logging system not initialized. Run 'setup' first.")
            sys.exit(1)

        results = logging_system.search_logs(
            args.query or "",
            args.logger,
            args.hours
        )

        print(f"🔍 Found {len(results)} matching log entries:")
        for entry in results[:10]:  # Show first 10
            print(f"  [{entry.get('timestamp')}] {entry.get('level')} {entry.get('message')}")

        if len(results) > 10:
            print(f"  ... and {len(results) - 10} more")

    elif args.action == "export":
        if not logging_system:
            print("❌ Logging system not initialized. Run 'setup' first.")
            sys.exit(1)

        filename = args.filename or f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_file = logging_system.export_logs(filename, args.hours, args.logger)
        print(f"📦 Logs exported to: {export_file}")

    elif args.action == "set-level":
        if not logging_system:
            print("❌ Logging system not initialized. Run 'setup' first.")
            sys.exit(1)

        if not args.new_level:
            print("❌ --new-level required")
            sys.exit(1)

        success = logging_system.runtime_manager.set_log_level(args.logger or "all", args.new_level)
        if success:
            print(f"✅ Log level changed to {args.new_level}")
        else:
            print(f"❌ Failed to change log level")

    elif args.action == "anomalies":
        if not logging_system:
            print("❌ Logging system not initialized. Run 'setup' first.")
            sys.exit(1)

        anomalies = logging_system.anomaly_detector.detect_anomalies()
        if anomalies:
            print("🚨 Detected Anomalies:")
            for anomaly in anomalies:
                print(f"  {anomaly['severity'].upper()}: {anomaly['description']}")
        else:
            print("✅ No anomalies detected")

if __name__ == "__main__":
    main()
