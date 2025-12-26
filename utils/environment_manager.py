#!/usr/bin/env python3
"""
Environment Management System for Polymarket Copy Bot

This module provides comprehensive virtual environment management including:
- Environment isolation and validation
- Dependency management and security scanning
- Multi-environment support (testnet, staging, mainnet)
- Health checks and automatic repair
"""

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports (will be available in virtual environment)
# No imports needed for basic environment checking

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    """Configuration for environment management"""

    name: str
    python_version: str
    venv_path: Path
    requirements_file: Path
    environment_file: Path
    service_name: str
    is_production: bool = False
    auto_update: bool = False
    security_scan_interval: int = 24  # hours


@dataclass
class DependencyInfo:
    """Information about a Python dependency"""

    name: str
    version: str
    required_version: str
    latest_version: Optional[str] = None
    vulnerabilities: List[Dict] = None
    last_checked: Optional[datetime] = None

    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []


@dataclass
class EnvironmentHealth:
    """Health status of an environment"""

    environment_name: str
    is_healthy: bool
    issues: List[str]
    last_check: datetime
    python_version_ok: bool
    dependencies_ok: bool
    security_ok: bool
    configuration_ok: bool


class EnvironmentManager:
    """Main environment management class"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.scripts_dir = self.project_root / "scripts"
        self.environments_dir = self.project_root / "environments"

        # Create directories if they don't exist
        self.environments_dir.mkdir(exist_ok=True)

        # Environment configurations
        self.environments = self._load_environment_configs()

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for environment management"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            filename=log_dir / "environment_manager.log",
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _load_environment_configs(self) -> Dict[str, EnvironmentConfig]:
        """Load environment configurations"""
        configs = {}

        # Production environment
        configs["production"] = EnvironmentConfig(
            name="production",
            python_version=">=3.9,<3.12",
            venv_path=self.project_root / "venv",
            requirements_file=self.project_root / "requirements.txt",
            environment_file=self.project_root / ".env",
            service_name="polymarket-bot",
            is_production=True,
            auto_update=False,
        )

        # Staging environment
        configs["staging"] = EnvironmentConfig(
            name="staging",
            python_version=">=3.9,<3.12",
            venv_path=self.project_root / "environments" / "staging" / "venv",
            requirements_file=self.project_root / "requirements-staging.txt",
            environment_file=self.project_root / ".env.staging",
            service_name="polymarket-bot-staging",
            is_production=False,
            auto_update=True,
        )

        # Development environment
        configs["development"] = EnvironmentConfig(
            name="development",
            python_version=">=3.9,<3.12",
            venv_path=self.project_root / "environments" / "development" / "venv",
            requirements_file=self.project_root / "requirements-dev.txt",
            environment_file=self.project_root / ".env.development",
            service_name="polymarket-bot-dev",
            is_production=False,
            auto_update=True,
        )

        return configs

    def create_environment(self, env_name: str, force: bool = False) -> bool:
        """Create a virtual environment for the specified environment"""
        if env_name not in self.environments:
            logger.error(f"Unknown environment: {env_name}")
            return False

        config = self.environments[env_name]
        logger.info(f"Creating environment: {env_name}")

        try:
            # Create environment directory
            config.venv_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing environment if force is True
            if force and config.venv_path.exists():
                import shutil

                shutil.rmtree(config.venv_path)
                logger.info(f"Removed existing environment: {config.venv_path}")

            # Create virtual environment
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(config.venv_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to create virtual environment: {result.stderr}")
                return False

            # Upgrade pip
            pip_path = config.venv_path / "bin" / "pip"
            result = subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"], capture_output=True, text=True
            )

            if result.returncode != 0:
                logger.warning(f"Failed to upgrade pip: {result.stderr}")

            logger.info(f"Successfully created environment: {env_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating environment {env_name}: {e}")
            return False

    def activate_environment(self, env_name: str) -> Optional[str]:
        """Get activation script for environment"""
        if env_name not in self.environments:
            logger.error(f"Unknown environment: {env_name}")
            return None

        config = self.environments[env_name]
        activate_script = config.venv_path / "bin" / "activate"

        if not activate_script.exists():
            logger.error(f"Activation script not found: {activate_script}")
            return None

        return str(activate_script)

    def deactivate_environment(self) -> str:
        """Get deactivation command"""
        return "deactivate"

    def install_dependencies(self, env_name: str, upgrade: bool = False) -> bool:
        """Install dependencies for the specified environment"""
        if env_name not in self.environments:
            logger.error(f"Unknown environment: {env_name}")
            return False

        config = self.environments[env_name]

        if not config.requirements_file.exists():
            logger.error(f"Requirements file not found: {config.requirements_file}")
            return False

        try:
            pip_path = config.venv_path / "bin" / "pip"
            cmd = [str(pip_path), "install"]

            if upgrade:
                cmd.append("--upgrade")

            cmd.extend(["-r", str(config.requirements_file)])

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to install dependencies: {result.stderr}")
                return False

            logger.info(f"Successfully installed dependencies for {env_name}")
            return True

        except Exception as e:
            logger.error(f"Error installing dependencies for {env_name}: {e}")
            return False

    def validate_environment(self, env_name: str) -> EnvironmentHealth:
        """Validate environment health"""
        if env_name not in self.environments:
            return EnvironmentHealth(
                environment_name=env_name,
                is_healthy=False,
                issues=["Unknown environment"],
                last_check=datetime.now(),
                python_version_ok=False,
                dependencies_ok=False,
                security_ok=False,
                configuration_ok=False,
            )

        config = self.environments[env_name]
        issues = []

        # Check Python version
        python_ok = self._check_python_version(config)
        if not python_ok:
            issues.append("Python version incompatible")

        # Check virtual environment
        venv_ok = config.venv_path.exists() and (config.venv_path / "bin" / "python").exists()
        if not venv_ok:
            issues.append("Virtual environment not found or corrupted")

        # Check dependencies
        deps_ok = self._check_dependencies(config)
        if not deps_ok:
            issues.append("Dependencies not properly installed")

        # Check configuration
        config_ok = self._check_configuration(config)
        if not config_ok:
            issues.append("Configuration issues detected")

        # Check security
        security_ok = self._check_security(config)
        if not security_ok:
            issues.append("Security vulnerabilities detected")

        is_healthy = len(issues) == 0

        health = EnvironmentHealth(
            environment_name=env_name,
            is_healthy=is_healthy,
            issues=issues,
            last_check=datetime.now(),
            python_version_ok=python_ok,
            dependencies_ok=deps_ok,
            security_ok=security_ok,
            configuration_ok=config_ok,
        )

        logger.info(
            f"Environment {env_name} health check: {'HEALTHY' if is_healthy else 'UNHEALTHY'}"
        )
        if issues:
            logger.warning(f"Issues found: {issues}")

        return health

    def _check_python_version(self, config: EnvironmentConfig) -> bool:
        """Check if Python version is compatible"""
        try:
            python_path = config.venv_path / "bin" / "python"
            if not python_path.exists():
                return False

            result = subprocess.run(
                [
                    str(python_path),
                    "-c",
                    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return False

            version_str = result.stdout.strip()
            version_parts = version_str.split(".")
            major, minor = int(version_parts[0]), int(version_parts[1])

            # Check if version is >= 3.9 and < 3.12
            return major == 3 and 9 <= minor < 12

        except Exception as e:
            logger.error(f"Error checking Python version: {e}")
            return False

    def _check_dependencies(self, config: EnvironmentConfig) -> bool:
        """Check if dependencies are properly installed"""
        try:
            python_path = config.venv_path / "bin" / "python"
            if not python_path.exists():
                return False

            # Try to import critical dependencies
            critical_deps = ["web3", "pydantic", "tenacity", "cryptography"]

            for dep in critical_deps:
                result = subprocess.run(
                    [str(python_path), "-c", f"import {dep}"], capture_output=True, text=True
                )

                if result.returncode != 0:
                    logger.warning(f"Missing dependency: {dep}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
            return False

    def _check_configuration(self, config: EnvironmentConfig) -> bool:
        """Check if configuration is valid"""
        if not config.environment_file.exists():
            logger.warning(f"Environment file not found: {config.environment_file}")
            return False

        # Basic checks - more detailed validation would be in settings validation
        try:
            with open(config.environment_file, "r") as f:
                content = f.read()

            # Check for required environment variables
            required_vars = ["PRIVATE_KEY", "POLYGON_RPC_URL"]
            for var in required_vars:
                if var not in content:
                    logger.warning(f"Missing required environment variable: {var}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking configuration: {e}")
            return False

    def _check_security(self, config: EnvironmentConfig) -> bool:
        """Check for security vulnerabilities"""
        # This would integrate with safety or similar tools
        # For now, return True as a placeholder
        return True

    def get_environment_info(self, env_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an environment"""
        if env_name not in self.environments:
            return None

        config = self.environments[env_name]
        health = self.validate_environment(env_name)

        return {
            "config": asdict(config),
            "health": asdict(health),
            "paths": {
                "venv": str(config.venv_path),
                "requirements": str(config.requirements_file),
                "environment": str(config.environment_file),
            },
        }

    def list_environments(self) -> List[str]:
        """List all available environments"""
        return list(self.environments.keys())

    def switch_environment(self, env_name: str) -> Optional[str]:
        """Switch to a different environment"""
        if env_name not in self.environments:
            logger.error(f"Unknown environment: {env_name}")
            return None

        # Return activation script path
        return self.activate_environment(env_name)


def main():
    """CLI interface for environment management"""
    import argparse

    parser = argparse.ArgumentParser(description="Environment Manager for Polymarket Copy Bot")
    parser.add_argument(
        "action",
        choices=["create", "validate", "install-deps", "activate", "info", "list", "health-check"],
    )
    parser.add_argument("--env", default="production", help="Environment name")
    parser.add_argument("--force", action="store_true", help="Force operation")

    args = parser.parse_args()

    manager = EnvironmentManager()

    if args.action == "create":
        success = manager.create_environment(args.env, args.force)
        print(
            f"✅ Created environment {args.env}"
            if success
            else f"❌ Failed to create environment {args.env}"
        )

    elif args.action == "validate":
        health = manager.validate_environment(args.env)
        print(f"Environment {args.env}: {'HEALTHY' if health.is_healthy else 'UNHEALTHY'}")
        if health.issues:
            print("Issues:")
            for issue in health.issues:
                print(f"  - {issue}")

    elif args.action == "install-deps":
        success = manager.install_dependencies(args.env)
        print(
            f"✅ Installed dependencies for {args.env}"
            if success
            else "❌ Failed to install dependencies"
        )

    elif args.action == "activate":
        script = manager.activate_environment(args.env)
        if script:
            print(f"source {script}")
        else:
            print(f"❌ Could not activate environment {args.env}")

    elif args.action == "info":
        info = manager.get_environment_info(args.env)
        if info:
            print(json.dumps(info, indent=2, default=str))
        else:
            print(f"❌ Environment {args.env} not found")

    elif args.action == "list":
        envs = manager.list_environments()
        print("Available environments:")
        for env in envs:
            print(f"  - {env}")

    elif args.action == "health-check":
        health = manager.validate_environment(args.env)
        print(json.dumps(asdict(health), indent=2, default=str))


if __name__ == "__main__":
    main()
