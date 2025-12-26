#!/usr/bin/env python3
"""
Multi-Environment Management System for Polymarket Copy Bot

This module provides support for multiple environments:
- Production (Mainnet)
- Staging (Testnet)
- Development (Local)
- Environment switching and isolation
- Network-specific configurations
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from environment_manager import EnvironmentManager
from dependency_manager import DependencyManager

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Network-specific configuration"""
    name: str
    display_name: str
    chain_id: int
    rpc_urls: List[str]
    block_explorer: str
    currency: str
    is_testnet: bool
    faucets: List[str] = field(default_factory=list)
    contracts: Dict[str, str] = field(default_factory=dict)


@dataclass
class EnvironmentSwitch:
    """Environment switch operation"""
    from_env: str
    to_env: str
    timestamp: datetime
    success: bool
    actions_taken: List[str]
    warnings: List[str]


class MultiEnvironmentManager:
    """Multi-environment management functionality"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.env_manager = EnvironmentManager(self.project_root)
        self.dep_manager = DependencyManager(self.project_root)

        # Network configurations
        self.networks = self._load_network_configs()

        # Current environment tracking
        self.current_env_file = self.project_root / ".current_env"

    def _load_network_configs(self) -> Dict[str, NetworkConfig]:
        """Load network configurations"""
        return {
            "polygon_mainnet": NetworkConfig(
                name="polygon_mainnet",
                display_name="Polygon Mainnet",
                chain_id=137,
                rpc_urls=[
                    "https://polygon-rpc.com/",
                    "https://rpc-mainnet.matic.network",
                    "https://matic-mainnet.chainstacklabs.com"
                ],
                block_explorer="https://polygonscan.com",
                currency="MATIC",
                is_testnet=False,
                contracts={
                    "clob": "0x5d6a3c37...2b6a",  # Real CLOB contract
                }
            ),
            "polygon_mumbai": NetworkConfig(
                name="polygon_mumbai",
                display_name="Polygon Mumbai Testnet",
                chain_id=80001,
                rpc_urls=[
                    "https://rpc-mumbai.maticvigil.com",
                    "https://matic-mumbai.chainstacklabs.com",
                    "https://rpc-mumbai.matic.today"
                ],
                block_explorer="https://mumbai.polygonscan.com",
                currency="MATIC",
                is_testnet=True,
                faucets=[
                    "https://faucet.polygon.technology/",
                    "https://matic.supply/"
                ],
                contracts={
                    "clob": "0x4b0c4c...8b6a",  # Testnet CLOB contract
                }
            ),
            "polygon_amoy": NetworkConfig(
                name="polygon_amoy",
                display_name="Polygon Amoy Testnet",
                chain_id=80002,
                rpc_urls=[
                    "https://rpc-amoy.polygon.technology",
                    "https://polygon-amoy.g.alchemy.com/v2/demo"
                ],
                block_explorer="https://amoy.polygonscan.com",
                currency="MATIC",
                is_testnet=True,
                faucets=[
                    "https://faucet.polygon.technology/",
                    "https://matic.supply/"
                ],
                contracts={
                    "clob": "0x4b0c4c...8b6a",  # Amoy CLOB contract
                }
            )
        }

    def get_current_environment(self) -> Optional[str]:
        """Get currently active environment"""
        if self.current_env_file.exists():
            try:
                return self.current_env_file.read_text().strip()
            except Exception:
                pass

        # Fallback: check environment variable
        return os.environ.get("POLYMARKET_ENV")

    def switch_environment(self, target_env: str, backup_current: bool = True) -> EnvironmentSwitch:
        """Switch to a different environment"""
        current_env = self.get_current_environment()

        switch = EnvironmentSwitch(
            from_env=current_env or "unknown",
            to_env=target_env,
            timestamp=datetime.now(),
            success=False,
            actions_taken=[],
            warnings=[]
        )

        try:
            # Validate target environment
            if target_env not in self.env_manager.environments:
                raise ValueError(f"Unknown environment: {target_env}")

            # Backup current environment state if requested
            if backup_current and current_env:
                backup_path = self._backup_environment_state(current_env)
                if backup_path:
                    switch.actions_taken.append(f"Backed up {current_env} to {backup_path}")
                else:
                    switch.warnings.append("Failed to backup current environment")

            # Stop current services
            if current_env:
                self._stop_environment_services(current_env)
                switch.actions_taken.append(f"Stopped services for {current_env}")

            # Validate target environment
            health = self.env_manager.validate_environment(target_env)
            if not health.is_healthy:
                switch.warnings.extend(health.issues)
                switch.actions_taken.append("Target environment has issues, attempting repair")

                # Attempt automatic repair
                from env_repair import EnvironmentRepair
                repair = EnvironmentRepair(self.project_root)
                repair_result = repair.diagnose_and_repair(target_env, auto_repair=True)

                if repair_result.success:
                    switch.actions_taken.append("Successfully repaired target environment")
                else:
                    switch.warnings.extend(repair_result.errors)
                    switch.actions_taken.append("Repair completed with warnings")

            # Update environment marker
            self.current_env_file.write_text(target_env)
            switch.actions_taken.append(f"Updated current environment to {target_env}")

            # Start target environment services
            self._start_environment_services(target_env)
            switch.actions_taken.append(f"Started services for {target_env}")

            # Set environment variables
            self._set_environment_variables(target_env)
            switch.actions_taken.append(f"Set environment variables for {target_env}")

            switch.success = True
            logger.info(f"Successfully switched from {current_env} to {target_env}")

        except Exception as e:
            switch.warnings.append(f"Switch failed: {str(e)}")
            logger.error(f"Environment switch failed: {e}")

        return switch

    def _backup_environment_state(self, environment: str) -> Optional[Path]:
        """Backup current environment state"""
        try:
            backup_dir = self.project_root / "backups" / "env_switches"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"env_switch_{environment}_{timestamp}"

            # Backup environment file
            config = self.env_manager.environments.get(environment)
            if config and config.environment_file.exists():
                shutil.copy(config.environment_file, backup_path / "environment")

            # Backup current environment marker
            if self.current_env_file.exists():
                shutil.copy(self.current_env_file, backup_path / "current_env")

            return backup_path

        except Exception as e:
            logger.error(f"Failed to backup environment state: {e}")
            return None

    def _stop_environment_services(self, environment: str) -> None:
        """Stop services for an environment"""
        try:
            if sys.platform.startswith('linux'):
                service_name = f"polymarket-bot{'-' + environment if environment != 'production' else ''}"
                import subprocess
                subprocess.run([
                    'systemctl', 'stop', service_name
                ], capture_output=True, check=False)
        except Exception as e:
            logger.warning(f"Failed to stop services for {environment}: {e}")

    def _start_environment_services(self, environment: str) -> None:
        """Start services for an environment"""
        try:
            if sys.platform.startswith('linux'):
                service_name = f"polymarket-bot{'-' + environment if environment != 'production' else ''}"
                import subprocess
                subprocess.run([
                    'systemctl', 'start', service_name
                ], capture_output=True, check=False)
        except Exception as e:
            logger.warning(f"Failed to start services for {environment}: {e}")

    def _set_environment_variables(self, environment: str) -> None:
        """Set environment-specific variables"""
        config = self.env_manager.environments.get(environment)
        if not config:
            return

        # Load environment file
        if config.environment_file.exists():
            try:
                import dotenv
                dotenv.load_dotenv(config.environment_file)
            except ImportError:
                # Fallback without dotenv
                with open(config.environment_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()

        # Set standard environment variables
        os.environ["POLYMARKET_ENV"] = environment
        os.environ["POLYMARKET_PROJECT_ROOT"] = str(self.project_root)

    def get_environment_network(self, environment: str) -> Optional[NetworkConfig]:
        """Get network configuration for an environment"""
        # Map environments to networks
        env_network_map = {
            "production": "polygon_mainnet",
            "staging": "polygon_mumbai",
            "development": "polygon_amoy"
        }

        network_name = env_network_map.get(environment)
        return self.networks.get(network_name) if network_name else None

    def validate_network_compatibility(self, environment: str) -> Dict[str, Any]:
        """Validate network compatibility for an environment"""
        result = {
            "compatible": True,
            "network": None,
            "issues": [],
            "recommendations": []
        }

        network = self.get_environment_network(environment)
        if not network:
            result["compatible"] = False
            result["issues"].append(f"No network configuration for environment: {environment}")
            return result

        result["network"] = {
            "name": network.name,
            "display_name": network.display_name,
            "is_testnet": network.is_testnet,
            "chain_id": network.chain_id
        }

        # Check if environment is configured for correct network
        config = self.env_manager.environments.get(environment)
        if config and config.environment_file.exists():
            try:
                with open(config.environment_file, 'r') as f:
                    env_content = f.read()

                # Check for network-specific settings
                if network.is_testnet:
                    if "CLOB_HOST" not in env_content or "clob.polymarket.com" in env_content:
                        result["issues"].append("Testnet environment should use testnet CLOB host")
                        result["recommendations"].append("Set CLOB_HOST=https://clob.polymarket.com (testnet)")
                else:
                    if "mainnet" not in env_content.lower() and "production" not in env_content.lower():
                        result["issues"].append("Mainnet environment should be clearly marked as production")

                if result["issues"]:
                    result["compatible"] = False

            except Exception as e:
                result["issues"].append(f"Failed to read environment file: {e}")
                result["compatible"] = False

        return result

    def create_environment_template(self, environment: str) -> Optional[Path]:
        """Create environment template with network-specific settings"""
        network = self.get_environment_network(environment)
        if not network:
            logger.error(f"No network configuration for environment: {environment}")
            return None

        template_path = self.project_root / f"env-{environment}-template.txt"

        try:
            with open(template_path, 'w') as f:
                f.write(f"# Environment template for {environment}\n")
                f.write(f"# Network: {network.display_name}\n")
                f.write(f"# Generated on {datetime.now().isoformat()}\n")
                f.write("\n")

                # Required settings
                f.write("# REQUIRED: Wallet Configuration\n")
                f.write(f"PRIVATE_KEY=your_{environment}_private_key_here\n")
                f.write("\n")

                # Network settings
                f.write("# REQUIRED: Network Configuration\n")
                f.write(f"POLYGON_RPC_URL={network.rpc_urls[0]}\n")
                f.write(f"CHAIN_ID={network.chain_id}\n")
                f.write(f"BLOCK_EXPLORER={network.block_explorer}\n")
                f.write("\n")

                # Polymarket settings
                f.write("# REQUIRED: Polymarket Configuration\n")
                if network.is_testnet:
                    f.write("CLOB_HOST=https://clob.polymarket.com\n")  # Testnet host
                else:
                    f.write("CLOB_HOST=https://clob.polymarket.com\n")  # Mainnet host
                f.write("\n")

                # Optional settings
                f.write("# OPTIONAL: Monitoring and Alerts\n")
                f.write("TELEGRAM_BOT_TOKEN=your_bot_token_here\n")
                f.write("TELEGRAM_CHAT_ID=your_chat_id_here\n")
                f.write("LOG_LEVEL=INFO\n")
                f.write("\n")

                # Risk settings
                f.write("# OPTIONAL: Risk Management\n")
                if network.is_testnet:
                    f.write("# Testnet - Conservative settings\n")
                    f.write("MAX_POSITION_SIZE=0.1\n")
                    f.write("MAX_DAILY_LOSS=0.05\n")
                    f.write("ENABLE_REAL_TRADING=false\n")
                else:
                    f.write("# Mainnet - Production settings\n")
                    f.write("MAX_POSITION_SIZE=1.0\n")
                    f.write("MAX_DAILY_LOSS=0.1\n")
                    f.write("ENABLE_REAL_TRADING=true\n")
                f.write("\n")

                # Environment info
                f.write("# Environment Information\n")
                f.write(f"POLYMARKET_ENV={environment}\n")
                f.write(f"NETWORK={network.name}\n")
                f.write(f"IS_TESTNET={network.is_testnet}\n")

            logger.info(f"Created environment template: {template_path}")
            return template_path

        except Exception as e:
            logger.error(f"Failed to create environment template: {e}")
            return None

    def list_available_environments(self) -> Dict[str, Dict[str, Any]]:
        """List all available environments with their status"""
        environments = {}

        for env_name in self.env_manager.environments.keys():
            health = self.env_manager.validate_environment(env_name)
            network_info = self.validate_network_compatibility(env_name)

            environments[env_name] = {
                "name": env_name,
                "healthy": health.is_healthy,
                "network": network_info.get("network"),
                "issues": health.issues + network_info.get("issues", []),
                "is_current": env_name == self.get_current_environment()
            }

        return environments

    def quick_switch(self, target_env: str) -> bool:
        """Quick environment switch without full validation"""
        try:
            # Just update the environment marker and variables
            self.current_env_file.write_text(target_env)
            self._set_environment_variables(target_env)

            logger.info(f"Quick switched to environment: {target_env}")
            return True

        except Exception as e:
            logger.error(f"Quick switch failed: {e}")
            return False


def main():
    """CLI interface for multi-environment management"""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Environment Manager for Polymarket Copy Bot")
    parser.add_argument("action", choices=[
        "switch", "current", "list", "validate-network", "create-template", "quick-switch"
    ])
    parser.add_argument("--env", help="Target environment name")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup during switch")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    manager = MultiEnvironmentManager()

    if args.action == "switch":
        if not args.env:
            print("❌ Target environment required")
            sys.exit(1)

        switch_result = manager.switch_environment(args.env, backup_current=not args.no_backup)
        print(f"Environment switch {'successful' if switch_result.success else 'failed'}")
        print(f"From: {switch_result.from_env} → To: {switch_result.to_env}")
        print(f"Actions: {switch_result.actions_taken}")
        if switch_result.warnings:
            print(f"Warnings: {switch_result.warnings}")

    elif args.action == "current":
        current = manager.get_current_environment()
        print(f"Current environment: {current or 'unknown'}")

    elif args.action == "list":
        envs = manager.list_available_environments()
        print("Available environments:")
        for name, info in envs.items():
            status = "✅" if info["healthy"] else "❌"
            current = " (current)" if info["is_current"] else ""
            network = info["network"]["display_name"] if info["network"] else "Unknown"
            print(f"  {status} {name}{current} - {network}")
            if info["issues"]:
                for issue in info["issues"]:
                    print(f"    ⚠️  {issue}")

    elif args.action == "validate-network":
        if not args.env:
            print("❌ Environment required")
            sys.exit(1)

        validation = manager.validate_network_compatibility(args.env)
        print(f"Network validation for {args.env}: {'✅ Compatible' if validation['compatible'] else '❌ Incompatible'}")
        if validation["issues"]:
            print("Issues:")
            for issue in validation["issues"]:
                print(f"  - {issue}")
        if validation["recommendations"]:
            print("Recommendations:")
            for rec in validation["recommendations"]:
                print(f"  - {rec}")

    elif args.action == "create-template":
        if not args.env:
            print("❌ Environment required")
            sys.exit(1)

        template_path = manager.create_environment_template(args.env)
        if template_path:
            print(f"✅ Created template: {template_path}")
        else:
            print("❌ Failed to create template")

    elif args.action == "quick-switch":
        if not args.env:
            print("❌ Target environment required")
            sys.exit(1)

        success = manager.quick_switch(args.env)
        print(f"Quick switch {'successful' if success else 'failed'}")


if __name__ == "__main__":
    main()
