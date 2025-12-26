#!/usr/bin/env python3
"""
Automatic Environment Repair System for Polymarket Copy Bot

This module provides automatic repair functionality for:
- Broken virtual environments
- Missing dependencies
- Configuration issues
- Permission problems
- Service failures
"""

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dependency_manager import DependencyManager
from environment_manager import EnvironmentHealth, EnvironmentManager

logger = logging.getLogger(__name__)


@dataclass
class RepairAction:
    """Represents a repair action"""

    issue: str
    action: str
    command: Optional[str] = None
    python_function: Optional[callable] = None
    risk_level: str = "low"  # low, medium, high
    requires_restart: bool = False


@dataclass
class RepairResult:
    """Result of a repair operation"""

    success: bool
    actions_taken: List[str]
    errors: List[str]
    requires_restart: bool
    timestamp: datetime


class EnvironmentRepair:
    """Automatic environment repair functionality"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.env_manager = EnvironmentManager(self.project_root)
        self.dep_manager = DependencyManager(self.project_root)

    def diagnose_and_repair(
        self, environment: str, auto_repair: bool = True, risk_level: str = "medium"
    ) -> RepairResult:
        """Diagnose environment issues and attempt automatic repair"""
        logger.info(f"Starting diagnosis and repair for environment: {environment}")

        actions_taken = []
        errors = []
        requires_restart = False

        try:
            # Get current health status
            health = self.env_manager.validate_environment(environment)

            if health.is_healthy:
                logger.info("Environment is already healthy")
                return RepairResult(
                    success=True,
                    actions_taken=["No repair needed - environment is healthy"],
                    errors=[],
                    requires_restart=False,
                    timestamp=datetime.now(),
                )

            # Generate repair plan
            repair_plan = self._generate_repair_plan(health, risk_level)

            if not auto_repair:
                # Just return the plan without executing
                return RepairResult(
                    success=False,
                    actions_taken=[f"Would repair: {action.issue}" for action in repair_plan],
                    errors=[],
                    requires_restart=any(action.requires_restart for action in repair_plan),
                    timestamp=datetime.now(),
                )

            # Execute repair plan
            for action in repair_plan:
                try:
                    logger.info(f"Executing repair: {action.action}")

                    if action.command:
                        self._execute_command(action.command)
                    elif action.python_function:
                        action.python_function()

                    actions_taken.append(action.action)
                    if action.requires_restart:
                        requires_restart = True

                except Exception as e:
                    error_msg = f"Failed to execute {action.action}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Re-validate after repair
            final_health = self.env_manager.validate_environment(environment)

            success = final_health.is_healthy and len(errors) == 0

            return RepairResult(
                success=success,
                actions_taken=actions_taken,
                errors=errors,
                requires_restart=requires_restart,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Repair process failed: {e}")
            return RepairResult(
                success=False,
                actions_taken=actions_taken,
                errors=[str(e)],
                requires_restart=False,
                timestamp=datetime.now(),
            )

    def _generate_repair_plan(self, health: EnvironmentHealth, max_risk: str) -> List[RepairAction]:
        """Generate a repair plan based on health status"""
        plan = []
        risk_levels = {"low": 0, "medium": 1, "high": 2}
        max_risk_level = risk_levels.get(max_risk, 1)

        # Python version issues
        if not health.python_version_ok:
            plan.append(
                RepairAction(
                    issue="Python version incompatible",
                    action="Update Python version or switch to compatible version",
                    risk_level="high",
                    requires_restart=True,
                )
            )

        # Virtual environment issues
        if not health.dependencies_ok or "Virtual environment not found" in health.issues:
            plan.append(
                RepairAction(
                    issue="Virtual environment corrupted or missing",
                    action="Recreate virtual environment",
                    python_function=lambda: self._repair_virtual_environment(
                        health.environment_name
                    ),
                    risk_level="medium",
                    requires_restart=True,
                )
            )

        # Dependency issues
        if not health.dependencies_ok:
            plan.append(
                RepairAction(
                    issue="Dependencies not properly installed",
                    action="Reinstall dependencies",
                    python_function=lambda: self._repair_dependencies(health.environment_name),
                    risk_level="low",
                    requires_restart=True,
                )
            )

        # Configuration issues
        if not health.configuration_ok:
            plan.append(
                RepairAction(
                    issue="Configuration issues detected",
                    action="Validate and fix configuration",
                    python_function=lambda: self._repair_configuration(health.environment_name),
                    risk_level="low",
                    requires_restart=False,
                )
            )

        # Security issues
        if not health.security_ok:
            plan.append(
                RepairAction(
                    issue="Security vulnerabilities detected",
                    action="Update vulnerable packages",
                    python_function=lambda: self._repair_security_issues(health.environment_name),
                    risk_level="medium",
                    requires_restart=True,
                )
            )

        # Filter by risk level
        filtered_plan = [
            action for action in plan if risk_levels.get(action.risk_level, 0) <= max_risk_level
        ]

        return filtered_plan

    def _repair_virtual_environment(self, environment: str) -> None:
        """Repair virtual environment"""
        logger.info(f"Repairing virtual environment for {environment}")

        # Force recreate environment
        success = self.env_manager.create_environment(environment, force=True)
        if not success:
            raise Exception("Failed to recreate virtual environment")

        # Reinstall dependencies
        success = self.dep_manager.install_dependencies(environment)
        if not success:
            raise Exception("Failed to reinstall dependencies")

    def _repair_dependencies(self, environment: str) -> None:
        """Repair dependency installation"""
        logger.info(f"Repairing dependencies for {environment}")

        # Reinstall dependencies
        success = self.dep_manager.install_dependencies(environment, upgrade=True)
        if not success:
            raise Exception("Failed to reinstall dependencies")

    def _repair_configuration(self, environment: str) -> None:
        """Repair configuration issues"""
        logger.info(f"Repairing configuration for {environment}")

        config = self.env_manager.environments.get(environment)
        if not config:
            raise Exception(f"Unknown environment: {environment}")

        # Check if environment file exists
        if not config.environment_file.exists():
            # Try to create from template
            template_file = self.project_root / f"env-{environment}-template.txt"
            if template_file.exists():
                shutil.copy(template_file, config.environment_file)
                logger.info(f"Created environment file from template: {config.environment_file}")
            else:
                raise Exception(f"No template available for environment: {environment}")

        # Set correct permissions
        config.environment_file.chmod(0o600)

    def _repair_security_issues(self, environment: str) -> None:
        """Repair security vulnerabilities"""
        logger.info(f"Repairing security issues for {environment}")

        # Update dependencies to latest secure versions
        updates = self.dep_manager.update_dependencies(environment, dry_run=False)

        if "errors" in updates and updates["errors"]:
            logger.warning(f"Some security updates failed: {updates['errors']}")

    def _execute_command(self, command: str) -> None:
        """Execute a shell command"""
        logger.info(f"Executing command: {command}")

        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, cwd=self.project_root
        )

        if result.returncode != 0:
            raise Exception(f"Command failed: {result.stderr}")

    def emergency_repair(self, environment: str) -> RepairResult:
        """Perform emergency repair - recreate everything"""
        logger.warning(f"Performing emergency repair for {environment}")

        actions_taken = []
        errors = []

        try:
            # Stop any running services
            self._stop_services(environment)
            actions_taken.append("Stopped running services")

            # Remove and recreate virtual environment
            config = self.env_manager.environments.get(environment)
            if config and config.venv_path.exists():
                shutil.rmtree(config.venv_path)
                actions_taken.append("Removed old virtual environment")

            # Recreate environment
            success = self.env_manager.create_environment(environment, force=True)
            if success:
                actions_taken.append("Recreated virtual environment")
            else:
                errors.append("Failed to recreate virtual environment")

            # Reinstall dependencies
            success = self.dep_manager.install_dependencies(environment)
            if success:
                actions_taken.append("Reinstalled dependencies")
            else:
                errors.append("Failed to reinstall dependencies")

            # Repair configuration
            self._repair_configuration(environment)
            actions_taken.append("Repaired configuration")

            # Restart services
            self._start_services(environment)
            actions_taken.append("Restarted services")

            return RepairResult(
                success=len(errors) == 0,
                actions_taken=actions_taken,
                errors=errors,
                requires_restart=True,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Emergency repair failed: {e}")
            return RepairResult(
                success=False,
                actions_taken=actions_taken,
                errors=[str(e)],
                requires_restart=False,
                timestamp=datetime.now(),
            )

    def _stop_services(self, environment: str) -> None:
        """Stop running services"""
        try:
            if sys.platform.startswith("linux"):
                service_name = (
                    f"polymarket-bot{'-' + environment if environment != 'production' else ''}"
                )
                subprocess.run(["systemctl", "stop", service_name], capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to stop services: {e}")

    def _start_services(self, environment: str) -> None:
        """Start services"""
        try:
            if sys.platform.startswith("linux"):
                service_name = (
                    f"polymarket-bot{'-' + environment if environment != 'production' else ''}"
                )
                subprocess.run(["systemctl", "start", service_name], capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to start services: {e}")

    def create_backup(self, environment: str) -> Optional[Path]:
        """Create backup of current environment"""
        try:
            backup_dir = self.project_root / "backups"
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"env_{environment}_backup_{timestamp}"

            config = self.env_manager.environments.get(environment)
            if config:
                # Backup virtual environment
                if config.venv_path.exists():
                    shutil.copytree(config.venv_path, backup_path / "venv")

                # Backup configuration
                if config.environment_file.exists():
                    shutil.copy(config.environment_file, backup_path / "env_file")

                logger.info(f"Created backup: {backup_path}")
                return backup_path

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")

        return None

    def restore_backup(self, backup_path: Path, environment: str) -> bool:
        """Restore environment from backup"""
        try:
            config = self.env_manager.environments.get(environment)
            if not config:
                return False

            backup_path = Path(backup_path)

            # Stop services
            self._stop_services(environment)

            # Restore virtual environment
            venv_backup = backup_path / "venv"
            if venv_backup.exists():
                if config.venv_path.exists():
                    shutil.rmtree(config.venv_path)
                shutil.copytree(venv_backup, config.venv_path)

            # Restore configuration
            env_backup = backup_path / "env_file"
            if env_backup.exists():
                shutil.copy(env_backup, config.environment_file)

            # Restart services
            self._start_services(environment)

            logger.info(f"Restored backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False


def main():
    """CLI interface for environment repair"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Environment Repair System for Polymarket Copy Bot"
    )
    parser.add_argument("action", choices=["repair", "diagnose", "emergency", "backup", "restore"])
    parser.add_argument("--env", default="production", help="Environment name")
    parser.add_argument("--auto", action="store_true", help="Automatically apply repairs")
    parser.add_argument(
        "--risk", choices=["low", "medium", "high"], default="medium", help="Maximum risk level"
    )
    parser.add_argument("--backup-path", help="Backup path for restore operation")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    repair = EnvironmentRepair()

    if args.action == "diagnose":
        result = repair.diagnose_and_repair(args.env, auto_repair=False)
        print("Diagnosis Results:")
        print(f"Actions needed: {len(result.actions_taken)}")
        for action in result.actions_taken:
            print(f"  - {action}")

    elif args.action == "repair":
        result = repair.diagnose_and_repair(args.env, auto_repair=args.auto, risk_level=args.risk)
        print(f"Repair {'successful' if result.success else 'failed'}")
        print(f"Actions taken: {result.actions_taken}")
        if result.errors:
            print(f"Errors: {result.errors}")
        if result.requires_restart:
            print("⚠️  Service restart required")

    elif args.action == "emergency":
        result = repair.emergency_repair(args.env)
        print(f"Emergency repair {'successful' if result.success else 'failed'}")
        print(f"Actions taken: {result.actions_taken}")
        if result.errors:
            print(f"Errors: {result.errors}")

    elif args.action == "backup":
        backup_path = repair.create_backup(args.env)
        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        else:
            print("❌ Backup failed")

    elif args.action == "restore":
        if not args.backup_path:
            print("❌ Backup path required for restore")
            sys.exit(1)

        success = repair.restore_backup(Path(args.backup_path), args.env)
        print(f"Restore {'successful' if success else 'failed'}")


if __name__ == "__main__":
    main()
