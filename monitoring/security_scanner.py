#!/usr/bin/env python3
"""
Automated Security Scanner
==========================

Performs comprehensive security scans including:
- Dependency vulnerability scanning
- Secret detection
- Configuration security validation
- Code security analysis
- Compliance checking

Runs daily and generates security reports.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from monitoring.monitoring_config import monitoring_config

logger = logging.getLogger(__name__)


class SecurityScanner:
    """Automated security scanner for the trading bot"""

    def __init__(self) -> None:
        self.config = monitoring_config.security
        self.scan_results = {}
        self.vulnerabilities_found = []
        self.alerts = []

    async def run_full_scan(self) -> Dict[str, Any]:
        """Run comprehensive security scan"""
        logger.info("🔒 Starting comprehensive security scan")

        scan_start = datetime.now()

        # Run all security checks
        checks = []

        if self.config.dependency_scan_enabled:
            checks.append(("dependency_scan", self._scan_dependencies()))

        if self.config.secrets_scan_enabled:
            checks.append(("secrets_scan", self._scan_secrets()))

        if self.config.config_scan_enabled:
            checks.append(("config_scan", self._scan_configuration()))

        if self.config.code_scan_enabled:
            checks.append(("code_scan", self._scan_code()))

        # Execute all checks concurrently
        results = {}
        for check_name, check_coro in checks:
            try:
                logger.info(f"Running {check_name}...")
                result = await check_coro
                results[check_name] = result
                logger.info(f"✅ {check_name} completed")
            except Exception as e:
                logger.error(f"❌ {check_name} failed: {e}")
                results[check_name] = {"error": str(e), "status": "failed"}

        scan_duration = (datetime.now() - scan_start).total_seconds()

        # Compile final report
        report = {
            "timestamp": scan_start.isoformat(),
            "duration_seconds": scan_duration,
            "results": results,
            "summary": self._generate_summary(results),
            "alerts": self.alerts,
            "recommendations": self._generate_recommendations(results),
        }

        # Save report
        await self._save_report(report)

        logger.info(f"🔒 Security scan completed in {scan_duration:.1f}s")
        return report

    async def _scan_dependencies(self) -> Dict[str, Any]:
        """Scan dependencies for vulnerabilities"""
        result = {
            "vulnerabilities": [],
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "status": "completed",
        }

        try:
            # Run safety check
            cmd = ["safety", "check", "--json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=".",
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # No vulnerabilities found
                logger.info("✅ No dependency vulnerabilities found")
            else:
                # Parse vulnerabilities
                try:
                    vulnerabilities = json.loads(stdout.decode())
                    result["vulnerabilities"] = vulnerabilities

                    # Count by severity
                    for vuln in vulnerabilities:
                        severity = vuln.get("severity", "unknown").lower()
                        if severity == "critical":
                            result["critical_count"] += 1
                        elif severity == "high":
                            result["high_count"] += 1
                        elif severity == "medium":
                            result["medium_count"] += 1
                        elif severity == "low":
                            result["low_count"] += 1

                    logger.warning(
                        f"⚠️ Found {len(vulnerabilities)} dependency vulnerabilities"
                    )

                    # Generate alerts for critical issues
                    if (
                        result["critical_count"]
                        > self.config.critical_vulnerabilities_threshold
                    ):
                        self.alerts.append(
                            {
                                "level": "critical",
                                "title": "Critical Dependency Vulnerabilities",
                                "message": f"Found {result['critical_count']} critical dependency vulnerabilities",
                                "details": vulnerabilities,
                            }
                        )

                except json.JSONDecodeError:
                    logger.error("Failed to parse safety output")
                    result["error"] = "Failed to parse safety output"

        except FileNotFoundError:
            logger.warning(
                "Safety tool not installed. Install with: pip install safety"
            )
            result["status"] = "tool_missing"
            result["error"] = "Safety tool not installed"

        return result

    async def _scan_secrets(self) -> Dict[str, Any]:
        """Scan for exposed secrets and sensitive data"""
        result = {"secrets_found": [], "files_scanned": 0, "status": "completed"}

        try:
            # Patterns to search for
            secret_patterns = [
                r"(?i)(api_key|apikey)\s*[=:]\s*['\"]([^'\"]{10,})['\"]",
                r"(?i)(secret|token)\s*[=:]\s*['\"]([^'\"]{10,})['\"]",
                r"(?i)(password|passwd)\s*[=:]\s*['\"]([^'\"]{6,})['\"]",
                r"(?i)0x[a-fA-F0-9]{64}",  # Private keys
                r"(?i)(BEGIN\s+(RSA\s+)?PRIVATE\s+KEY)",
            ]

            # Files to exclude
            exclude_patterns = [
                ".git",
                "__pycache__",
                "venv",
                "node_modules",
                "*.pyc",
                "*.log",
                ".env*",
                "monitoring/security/secrets_scan.log",
            ]

            secrets_found = []
            files_scanned = 0

            # Scan Python files
            for py_file in Path(".").rglob("*.py"):
                # Check if file should be excluded
                if any(excl in str(py_file) for excl in exclude_patterns):
                    continue

                files_scanned += 1

                try:
                    content = py_file.read_text()

                    for pattern in secret_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            for match in matches:
                                # Don't log actual secrets in alerts
                                secrets_found.append(
                                    {
                                        "file": str(py_file),
                                        "pattern": pattern,
                                        "line_count": len(matches),
                                        "masked_secret": "***SECRET_FOUND***",
                                    }
                                )

                except Exception as e:
                    logger.debug(f"Could not scan {py_file}: {e}")

            result["secrets_found"] = secrets_found
            result["files_scanned"] = files_scanned

            if secrets_found:
                logger.warning(
                    f"⚠️ Found potential secrets in {len(secrets_found)} locations"
                )

                if len(secrets_found) > self.config.secrets_found_threshold:
                    self.alerts.append(
                        {
                            "level": "high",
                            "title": "Potential Secrets Exposed",
                            "message": f"Found {len(secrets_found)} potential secrets in codebase",
                            "details": [
                                {"file": s["file"], "pattern": s["pattern"]}
                                for s in secrets_found
                            ],
                        }
                    )

        except Exception as e:
            logger.error(f"Error during secrets scan: {e}")
            result["error"] = str(e)
            result["status"] = "failed"

        return result

    async def _scan_configuration(self) -> Dict[str, Any]:
        """Scan configuration files for security issues"""
        result = {"issues": [], "files_checked": [], "status": "completed"}

        # Configuration files to check
        config_files = [
            ".env",
            ".env.staging",
            "config/settings.py",
            "config/settings_staging.py",
            "config/wallets.json",
            "config/wallets_staging.json",
        ]

        issues = []

        for config_file in config_files:
            if os.path.exists(config_file):
                result["files_checked"].append(config_file)

                try:
                    # Check file permissions
                    stat_info = os.stat(config_file)
                    permissions = oct(stat_info.st_mode)[-3:]

                    # Alert on overly permissive files
                    if (
                        config_file.startswith((".env", "config/"))
                        and permissions != "600"
                    ):
                        issues.append(
                            {
                                "file": config_file,
                                "issue": "insecure_permissions",
                                "severity": "high",
                                "description": f"File has permissions {permissions}, should be 600",
                                "recommendation": "Run: chmod 600 {config_file}",
                            }
                        )

                    # Check for hardcoded secrets in config files
                    if config_file.endswith((".py", ".json")):
                        with open(config_file, "r") as f:
                            content = f.read()

                        # Look for potential secrets
                        if re.search(r"0x[a-fA-F0-9]{64}", content):  # Private keys
                            issues.append(
                                {
                                    "file": config_file,
                                    "issue": "hardcoded_private_key",
                                    "severity": "critical",
                                    "description": "Potential hardcoded private key found",
                                    "recommendation": "Move private keys to environment variables",
                                }
                            )

                except Exception as e:
                    logger.debug(f"Could not check {config_file}: {e}")

        result["issues"] = issues

        if issues:
            critical_issues = [i for i in issues if i["severity"] == "critical"]
            if critical_issues:
                self.alerts.append(
                    {
                        "level": "critical",
                        "title": "Critical Configuration Security Issues",
                        "message": f"Found {len(critical_issues)} critical configuration security issues",
                        "details": critical_issues,
                    }
                )

        return result

    async def _scan_code(self) -> Dict[str, Any]:
        """Perform static code security analysis"""
        result = {"issues": [], "files_analyzed": 0, "status": "completed"}

        try:
            # Run Bandit security linter
            cmd = ["bandit", "-r", ".", "-f", "json", "-q"]

            # Add exclude directories
            for exclude_dir in self.config.bandit_config.get("exclude_dirs", []):
                cmd.extend(["--exclude", exclude_dir])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=".",
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # No issues found
                logger.info("✅ No code security issues found")
            else:
                try:
                    bandit_results = json.loads(stdout.decode())
                    result["issues"] = bandit_results.get("results", [])
                    result["files_analyzed"] = len(bandit_results.get("files_list", []))

                    # Count issues by severity
                    severity_counts = {}
                    for issue in result["issues"]:
                        severity = issue.get("issue_severity", "unknown")
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

                    logger.warning(
                        f"⚠️ Found {len(result['issues'])} code security issues"
                    )

                except json.JSONDecodeError:
                    logger.error("Failed to parse bandit output")
                    result["error"] = "Failed to parse bandit output"

        except FileNotFoundError:
            logger.warning(
                "Bandit tool not installed. Install with: pip install bandit"
            )
            result["status"] = "tool_missing"
            result["error"] = "Bandit tool not installed"

        return result

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate security scan summary"""
        summary = {
            "overall_status": "passed",
            "total_issues": 0,
            "critical_issues": 0,
            "high_issues": 0,
            "scan_components": len(results),
        }

        # Aggregate issues from all scans
        for scan_name, scan_result in results.items():
            if scan_result.get("status") == "failed":
                summary["overall_status"] = "failed"
                continue

            # Count vulnerabilities
            if scan_name == "dependency_scan":
                summary["total_issues"] += len(scan_result.get("vulnerabilities", []))
                summary["critical_issues"] += scan_result.get("critical_count", 0)
                summary["high_issues"] += scan_result.get("high_count", 0)

            elif scan_name == "secrets_scan":
                secrets_count = len(scan_result.get("secrets_found", []))
                summary["total_issues"] += secrets_count
                if secrets_count > 0:
                    summary["high_issues"] += secrets_count

            elif scan_name == "config_scan":
                config_issues = scan_result.get("issues", [])
                summary["total_issues"] += len(config_issues)
                for issue in config_issues:
                    if issue.get("severity") == "critical":
                        summary["critical_issues"] += 1
                    elif issue.get("severity") == "high":
                        summary["high_issues"] += 1

            elif scan_name == "code_scan":
                code_issues = scan_result.get("issues", [])
                summary["total_issues"] += len(code_issues)
                # Code issues are typically medium/low severity

        # Determine overall status
        if summary["critical_issues"] > 0:
            summary["overall_status"] = "critical"
        elif summary["high_issues"] > self.config.high_vulnerabilities_threshold:
            summary["overall_status"] = "high"
        elif summary["total_issues"] > 0:
            summary["overall_status"] = "warning"

        return summary

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate security recommendations based on scan results"""
        recommendations = []

        # Dependency recommendations
        dep_result = results.get("dependency_scan", {})
        if dep_result.get("critical_count", 0) > 0:
            recommendations.append(
                "🚨 Update critical dependency vulnerabilities immediately"
            )
        if dep_result.get("high_count", 0) > 0:
            recommendations.append(
                "⚠️ Review and update high-severity dependency vulnerabilities"
            )

        # Secrets recommendations
        secrets_result = results.get("secrets_scan", {})
        if secrets_result.get("secrets_found", []):
            recommendations.append(
                "🔐 Remove exposed secrets from codebase and rotate compromised credentials"
            )

        # Configuration recommendations
        config_result = results.get("config_scan", {})
        config_issues = config_result.get("issues", [])
        if config_issues:
            recommendations.append(
                "🔒 Fix configuration security issues (permissions, hardcoded secrets)"
            )

        # Code recommendations
        code_result = results.get("code_scan", {})
        code_issues = code_result.get("issues", [])
        if code_issues:
            recommendations.append(
                "💻 Address code security issues identified by static analysis"
            )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "✅ Security posture is good - continue regular scanning"
            )

        return recommendations

    async def _save_report(self, report: Dict[str, Any]) -> None:
        """Save security scan report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"monitoring/security/security_scan_{timestamp}.json"

        # Ensure directory exists
        Path("monitoring/security").mkdir(parents=True, exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"💾 Security scan report saved to {report_file}")

        # Also save latest report
        latest_file = "monitoring/security/latest_security_scan.json"
        with open(latest_file, "w") as f:
            json.dump(report, f, indent=2, default=str)


async def run_daily_security_scan() -> Dict[str, Any]:
    """Run the daily security scan"""
    scanner = SecurityScanner()
    report = await scanner.run_full_scan()

    # Log summary
    summary = report.get("summary", {})
    logger.info(
        f"🔒 Security Scan Summary: {summary.get('overall_status', 'unknown').upper()}"
    )
    logger.info(f"   Total Issues: {summary.get('total_issues', 0)}")
    logger.info(f"   Critical: {summary.get('critical_issues', 0)}")
    logger.info(f"   High: {summary.get('high_issues', 0)}")

    return report


if __name__ == "__main__":
    # Run security scan
    asyncio.run(run_daily_security_scan())
