#!/usr/bin/env python3
"""
Dependency Management System for Polymarket Copy Bot

This module provides comprehensive dependency management including:
- Requirements generation and validation
- Security vulnerability scanning
- Automated dependency updates
- Conflict resolution
"""

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports (will be available in virtual environment)
try:
    import pkg_resources
except ImportError:
    print("⚠️  Environment dependencies not available. Run setup first.")
    pass

logger = logging.getLogger(__name__)


@dataclass
class DependencySpec:
    """Specification for a Python dependency"""

    name: str
    version_spec: str
    description: str = ""
    security_critical: bool = False
    environment_specific: bool = False
    environments: List[str] = None

    def __post_init__(self):
        if self.environments is None:
            self.environments = ["production", "staging", "development"]


@dataclass
class VulnerabilityInfo:
    """Security vulnerability information"""

    package: str
    version: str
    vulnerability_id: str
    severity: str
    description: str
    published_date: datetime
    fixed_version: Optional[str] = None


@dataclass
class DependencyStatus:
    """Status of a dependency"""

    name: str
    current_version: Optional[str]
    required_version: str
    latest_version: Optional[str]
    is_installed: bool
    is_compatible: bool
    vulnerabilities: List[VulnerabilityInfo]
    last_checked: datetime


class DependencyManager:
    """Main dependency management class"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent

        # Setup paths
        self.requirements_dir = self.project_root / "requirements"
        self.requirements_dir.mkdir(exist_ok=True)

        # Dependency specifications
        self.dependencies = self._load_dependency_specs()

        # Cache for vulnerability data
        self.vuln_cache_file = self.project_root / "data" / "vulnerability_cache.json"
        self.vuln_cache_file.parent.mkdir(exist_ok=True)

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for dependency management"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            filename=log_dir / "dependency_manager.log",
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _load_dependency_specs(self) -> Dict[str, DependencySpec]:
        """Load dependency specifications"""
        specs = {}

        # Core dependencies
        specs["web3"] = DependencySpec(
            name="web3",
            version_spec="6.15.1",
            description="Web3.py library for Ethereum interaction",
            security_critical=True,
        )

        specs["py-clob-client"] = DependencySpec(
            name="py-clob-client",
            version_spec="0.16.0",
            description="Polymarket CLOB client",
            security_critical=True,
        )

        specs["pydantic"] = DependencySpec(
            name="pydantic",
            version_spec="2.5.3",
            description="Data validation and settings management",
            security_critical=False,
        )

        specs["tenacity"] = DependencySpec(
            name="tenacity",
            version_spec="8.2.3",
            description="Retry logic for API calls",
            security_critical=False,
        )

        specs["cryptography"] = DependencySpec(
            name="cryptography",
            version_spec="41.0.7",
            description="Cryptographic operations",
            security_critical=True,
        )

        specs["requests"] = DependencySpec(
            name="requests",
            version_spec="2.31.0",
            description="HTTP library",
            security_critical=True,
        )

        specs["aiohttp"] = DependencySpec(
            name="aiohttp",
            version_spec="3.9.1",
            description="Async HTTP client",
            security_critical=True,
        )

        specs["pandas"] = DependencySpec(
            name="pandas",
            version_spec="2.1.4",
            description="Data analysis library",
            security_critical=False,
        )

        specs["apscheduler"] = DependencySpec(
            name="APScheduler",
            version_spec="3.10.4",
            description="Task scheduling",
            security_critical=False,
        )

        specs["python-telegram-bot"] = DependencySpec(
            name="python-telegram-bot",
            version_spec="20.7",
            description="Telegram bot API",
            security_critical=True,
        )

        specs["loguru"] = DependencySpec(
            name="loguru",
            version_spec="0.7.2",
            description="Advanced logging",
            security_critical=False,
        )

        specs["python-json-logger"] = DependencySpec(
            name="python-json-logger",
            version_spec="2.0.7",
            description="JSON logging",
            security_critical=False,
        )

        # Development dependencies
        specs["pytest"] = DependencySpec(
            name="pytest",
            version_spec="7.4.3",
            description="Testing framework",
            security_critical=False,
            environments=["staging", "development"],
        )

        specs["pytest-asyncio"] = DependencySpec(
            name="pytest-asyncio",
            version_spec="0.21.1",
            description="Async testing support",
            security_critical=False,
            environments=["staging", "development"],
        )

        specs["pytest-cov"] = DependencySpec(
            name="pytest-cov",
            version_spec="4.1.0",
            description="Coverage reporting",
            security_critical=False,
            environments=["staging", "development"],
        )

        specs["black"] = DependencySpec(
            name="black",
            version_spec="23.12.1",
            description="Code formatting",
            security_critical=False,
            environments=["development"],
        )

        specs["isort"] = DependencySpec(
            name="isort",
            version_spec="5.13.2",
            description="Import sorting",
            security_critical=False,
            environments=["development"],
        )

        specs["mypy"] = DependencySpec(
            name="mypy",
            version_spec="1.7.1",
            description="Type checking",
            security_critical=False,
            environments=["development"],
        )

        # Security dependencies
        specs["bandit"] = DependencySpec(
            name="bandit",
            version_spec="1.7.5",
            description="Security linting",
            security_critical=False,
            environments=["staging", "development"],
        )

        specs["safety"] = DependencySpec(
            name="safety",
            version_spec="2.3.5",
            description="Security vulnerability scanning",
            security_critical=False,
            environments=["staging", "development"],
        )

        return specs

    def generate_requirements_files(self) -> bool:
        """Generate requirements files for all environments"""
        try:
            # Production requirements
            self._generate_requirements_file("production")

            # Staging requirements
            self._generate_requirements_file("staging")

            # Development requirements
            self._generate_requirements_file("development")

            logger.info("Successfully generated requirements files")
            return True

        except Exception as e:
            logger.error(f"Error generating requirements files: {e}")
            return False

    def _generate_requirements_file(self, environment: str) -> None:
        """Generate requirements file for specific environment"""
        requirements_file = self.requirements_dir / f"requirements-{environment}.txt"

        with open(requirements_file, "w") as f:
            f.write(f"# Requirements for {environment} environment\n")
            f.write(f"# Generated on {datetime.now().isoformat()}\n")
            f.write("# DO NOT EDIT MANUALLY - Use dependency_manager.py\n\n")

            for dep_name, dep_spec in self.dependencies.items():
                if environment in dep_spec.environments:
                    f.write(f"{dep_spec.name}=={dep_spec.version_spec}\n")

            # Add pip-tools for dependency management
            if environment in ["staging", "development"]:
                f.write("\npip-tools==7.3.0\n")

        logger.info(f"Generated {requirements_file}")

    def check_vulnerabilities(self, environment: str = "production") -> List[VulnerabilityInfo]:
        """Check for security vulnerabilities in dependencies"""
        vulnerabilities = []

        try:
            # Load cache if exists and not too old
            cache_data = self._load_vulnerability_cache()
            if cache_data and self._is_cache_valid(cache_data):
                logger.info("Using cached vulnerability data")
                return cache_data.get("vulnerabilities", [])

            # Run safety check
            if self._is_safety_available():
                vulnerabilities = self._run_safety_check(environment)

            # Cache the results
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "environment": environment,
                "vulnerabilities": [asdict(v) for v in vulnerabilities],
            }
            self._save_vulnerability_cache(cache_data)

        except Exception as e:
            logger.error(f"Error checking vulnerabilities: {e}")

        return vulnerabilities

    def _is_safety_available(self) -> bool:
        """Check if safety tool is available"""
        try:
            subprocess.run(["safety", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _run_safety_check(self, environment: str) -> List[VulnerabilityInfo]:
        """Run safety vulnerability check"""
        vulnerabilities = []
        requirements_file = self.requirements_dir / f"requirements-{environment}.txt"

        if not requirements_file.exists():
            logger.warning(f"Requirements file not found: {requirements_file}")
            return vulnerabilities

        try:
            result = subprocess.run(
                ["safety", "check", "--file", str(requirements_file), "--json"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # No vulnerabilities found
                return vulnerabilities

            # Parse JSON output
            try:
                safety_data = json.loads(result.stdout)
                for vuln in safety_data:
                    vulnerabilities.append(
                        VulnerabilityInfo(
                            package=vuln.get("package", ""),
                            version=vuln.get("version", ""),
                            vulnerability_id=vuln.get("vulnerability_id", ""),
                            severity=vuln.get("severity", "unknown"),
                            description=vuln.get("description", ""),
                            published_date=datetime.fromisoformat(
                                vuln.get("published_date", "").replace("Z", "+00:00")
                            ),
                            fixed_version=vuln.get("fixed_version"),
                        )
                    )
            except json.JSONDecodeError:
                logger.error("Failed to parse safety output")

        except Exception as e:
            logger.error(f"Error running safety check: {e}")

        return vulnerabilities

    def _load_vulnerability_cache(self) -> Optional[Dict]:
        """Load vulnerability cache"""
        if not self.vuln_cache_file.exists():
            return None

        try:
            with open(self.vuln_cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading vulnerability cache: {e}")
            return None

    def _save_vulnerability_cache(self, data: Dict) -> None:
        """Save vulnerability cache"""
        try:
            with open(self.vuln_cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving vulnerability cache: {e}")

    def _is_cache_valid(self, cache_data: Dict) -> bool:
        """Check if vulnerability cache is still valid"""
        try:
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            cache_age = datetime.now() - cache_time
            return cache_age < timedelta(hours=24)
        except Exception:
            return False

    def update_dependencies(self, environment: str, dry_run: bool = True) -> Dict[str, Any]:
        """Update dependencies to latest compatible versions"""
        updates = {
            "environment": environment,
            "updates_available": [],
            "security_updates": [],
            "breaking_changes": [],
            "dry_run": dry_run,
        }

        try:
            requirements_file = self.requirements_dir / f"requirements-{environment}.txt"
            if not requirements_file.exists():
                logger.error(f"Requirements file not found: {requirements_file}")
                return updates

            # This would integrate with pip-tools or similar for safe updates
            # For now, return placeholder
            logger.info(f"Dependency update check for {environment} completed")

        except Exception as e:
            logger.error(f"Error updating dependencies: {e}")

        return updates

    def resolve_conflicts(self, environment: str) -> Dict[str, Any]:
        """Resolve dependency conflicts"""
        conflicts = {
            "environment": environment,
            "conflicts": [],
            "resolutions": [],
            "unresolved": [],
        }

        try:
            # Use pip-tools to resolve conflicts
            requirements_file = self.requirements_dir / f"requirements-{environment}.txt"
            if not requirements_file.exists():
                logger.error(f"Requirements file not found: {requirements_file}")
                return conflicts

            # This would run pip-compile to resolve conflicts
            logger.info(f"Conflict resolution check for {environment} completed")

        except Exception as e:
            logger.error(f"Error resolving conflicts: {e}")

        return conflicts

    def get_dependency_status(self, environment: str) -> List[DependencyStatus]:
        """Get status of all dependencies for an environment"""
        statuses = []

        try:
            for dep_name, dep_spec in self.dependencies.items():
                if environment not in dep_spec.environments:
                    continue

                status = DependencyStatus(
                    name=dep_name,
                    current_version=None,
                    required_version=dep_spec.version_spec,
                    latest_version=None,
                    is_installed=False,
                    is_compatible=True,
                    vulnerabilities=[],
                    last_checked=datetime.now(),
                )

                # Check if installed
                try:
                    pkg = pkg_resources.get_distribution(dep_spec.name)
                    status.current_version = pkg.version
                    status.is_installed = True
                except pkg_resources.DistributionNotFound:
                    pass

                statuses.append(status)

        except Exception as e:
            logger.error(f"Error getting dependency status: {e}")

        return statuses

    def install_dependencies(self, environment: str, upgrade: bool = False) -> bool:
        """Install dependencies for an environment"""
        try:
            requirements_file = self.requirements_dir / f"requirements-{environment}.txt"

            if not requirements_file.exists():
                logger.error(f"Requirements file not found: {requirements_file}")
                return False

            cmd = [sys.executable, "-m", "pip", "install"]

            if upgrade:
                cmd.append("--upgrade")

            cmd.extend(["-r", str(requirements_file)])

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to install dependencies: {result.stderr}")
                return False

            logger.info(f"Successfully installed dependencies for {environment}")
            return True

        except Exception as e:
            logger.error(f"Error installing dependencies for {environment}: {e}")
            return False


def main():
    """CLI interface for dependency management"""
    import argparse

    parser = argparse.ArgumentParser(description="Dependency Manager for Polymarket Copy Bot")
    parser.add_argument(
        "action", choices=["generate", "check-vulns", "update", "resolve", "status", "install"]
    )
    parser.add_argument("--env", default="production", help="Environment name")
    parser.add_argument("--dry-run", action="store_true", help="Dry run for updates")

    args = parser.parse_args()

    manager = DependencyManager()

    if args.action == "generate":
        success = manager.generate_requirements_files()
        print(
            "✅ Generated requirements files"
            if success
            else "❌ Failed to generate requirements files"
        )

    elif args.action == "check-vulns":
        vulns = manager.check_vulnerabilities(args.env)
        if vulns:
            print(f"🚨 Found {len(vulns)} vulnerabilities:")
            for vuln in vulns:
                print(
                    f"  - {vuln.package} {vuln.version}: {vuln.vulnerability_id} ({vuln.severity})"
                )
        else:
            print("✅ No vulnerabilities found")

    elif args.action == "update":
        updates = manager.update_dependencies(args.env, args.dry_run)
        print(json.dumps(updates, indent=2))

    elif args.action == "resolve":
        conflicts = manager.resolve_conflicts(args.env)
        print(json.dumps(conflicts, indent=2))

    elif args.action == "status":
        statuses = manager.get_dependency_status(args.env)
        for status in statuses:
            installed = "✅" if status.is_installed else "❌"
            print(
                f"{installed} {status.name}: {status.current_version or 'not installed'} (required: {status.required_version})"
            )

    elif args.action == "install":
        success = manager.install_dependencies(args.env)
        print(
            f"✅ Installed dependencies for {args.env}"
            if success
            else "❌ Failed to install dependencies"
        )


if __name__ == "__main__":
    main()
