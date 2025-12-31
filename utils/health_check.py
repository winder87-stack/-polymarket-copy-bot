#!/usr/bin/env python3
"""
Environment Health Check System for Polymarket Copy Bot

This module provides comprehensive health checking for:
- Environment validation
- Service health monitoring
- Dependency status
- Security checks
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

# Third-party imports
try:
    import uvicorn
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError:
    FastAPI = None
    print("⚠️  FastAPI not available. Health check endpoints disabled.")

from dependency_manager import DependencyManager
from environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)


class HealthStatus(BaseModel):
    """Health status response model"""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    version: str
    environment: str
    checks: Dict[str, Any]
    issues: List[str]


class SystemHealthCheck:
    """System health check functionality"""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path(__file__).parent.parent
        self.env_manager = EnvironmentManager(self.project_root)
        self.dep_manager = DependencyManager(self.project_root)

    async def check_overall_health(
        self, environment: str = "production"
    ) -> HealthStatus:
        """Perform comprehensive health check"""
        checks = {}
        issues = []

        # Environment check
        try:
            env_health = self.env_manager.validate_environment(environment)
            checks["environment"] = {
                "healthy": env_health.is_healthy,
                "python_ok": env_health.python_version_ok,
                "deps_ok": env_health.dependencies_ok,
                "config_ok": env_health.configuration_ok,
                "security_ok": env_health.security_ok,
            }
            if not env_health.is_healthy:
                issues.extend(env_health.issues)
        except Exception as e:
            checks["environment"] = {"error": str(e)}
            issues.append(f"Environment check failed: {e}")

        # Dependency check
        try:
            dep_statuses = self.dep_manager.get_dependency_status(environment)
            critical_deps = [
                s
                for s in dep_statuses
                if any(
                    spec.security_critical
                    for spec in self.dep_manager.dependencies.values()
                    if spec.name == s.name
                )
            ]

            checks["dependencies"] = {
                "total": len(dep_statuses),
                "installed": len([s for s in dep_statuses if s.is_installed]),
                "critical_installed": len([s for s in critical_deps if s.is_installed]),
                "vulnerabilities": len(
                    self.dep_manager.check_vulnerabilities(environment)
                ),
            }

            missing_critical = [s.name for s in critical_deps if not s.is_installed]
            if missing_critical:
                issues.append(f"Missing critical dependencies: {missing_critical}")
        except Exception as e:
            checks["dependencies"] = {"error": str(e)}
            issues.append(f"Dependency check failed: {e}")

        # System resources check
        try:
            checks["system"] = self._check_system_resources()
        except Exception as e:
            checks["system"] = {"error": str(e)}
            issues.append(f"System check failed: {e}")

        # Service check (if applicable)
        try:
            checks["services"] = self._check_services(environment)
        except Exception as e:
            checks["services"] = {"error": str(e)}
            issues.append(f"Service check failed: {e}")

        # Determine overall status
        if issues:
            status = "degraded" if len(issues) < 3 else "unhealthy"
        else:
            status = "healthy"

        return HealthStatus(
            status=status,
            timestamp=datetime.now(),
            version=self._get_version(),
            environment=environment,
            checks=checks,
            issues=issues,
        )

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage(self.project_root).percent,
            "memory_available_gb": round(
                psutil.virtual_memory().available / (1024**3), 2
            ),
            "disk_available_gb": round(
                psutil.disk_usage(self.project_root).free / (1024**3), 2
            ),
        }

    def _check_services(self, environment: str) -> Dict[str, Any]:
        """Check service status"""
        services = {}

        # Check if bot process is running
        bot_running = False
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "python" in proc.info["name"].lower():
                    cmdline = " ".join(proc.info["cmdline"])
                    if "main.py" in cmdline and str(self.project_root) in cmdline:
                        bot_running = True
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        services["bot_process"] = bot_running

        # Check systemd service status (Linux only)
        if sys.platform.startswith("linux"):
            try:
                import subprocess

                service_name = f"polymarket-bot{'-' + environment if environment != 'production' else ''}"
                result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True,
                    text=True,
                )

                services["systemd_service"] = result.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
                logger.debug(f"Failed to check systemd service: {e}")
                services["systemd_service"] = "unknown"

        return services

    def _get_version(self) -> str:
        """Get current version"""
        try:
            version_file = self.project_root / "VERSION"
            if version_file.exists():
                return version_file.read_text().strip()

            # Try pyproject.toml
            pyproject_file = self.project_root / "pyproject.toml"
            if pyproject_file.exists():
                import tomllib

                with open(pyproject_file, "rb") as f:
                    data = tomllib.load(f)
                return data.get("tool", {}).get("poetry", {}).get("version", "unknown")

        except (IOError, OSError, KeyError) as e:
            logger.debug(f"Failed to read version: {e}")
            pass
        except Exception as e:
            # Handle tomllib-specific errors separately
            logger.debug(f"Failed to parse version: {e}")
            pass

        return "unknown"

    async def check_environment_reproduction(self, environment: str) -> Dict[str, Any]:
        """Check if environment can be reproduced"""
        result = {"reproducible": True, "issues": [], "recommendations": []}

        try:
            # Check requirements files
            requirements_dir = self.project_root / "requirements"
            req_file = requirements_dir / f"requirements-{environment}.txt"

            if not req_file.exists():
                result["reproducible"] = False
                result["issues"].append("Requirements file missing")
                result["recommendations"].append(
                    "Run: python utils/dependency_manager.py generate"
                )

            # Check environment template
            env_template = self.project_root / f"env-{environment}-template.txt"
            if not env_template.exists():
                result["issues"].append("Environment template missing")
                result["recommendations"].append(f"Create {env_template}")

            # Check setup script
            setup_script = self.project_root / "scripts" / "env_setup.sh"
            if not setup_script.exists():
                result["reproducible"] = False
                result["issues"].append("Setup script missing")

        except Exception as e:
            result["reproducible"] = False
            result["issues"].append(f"Reproducibility check failed: {e}")

        return result


# FastAPI app for health check endpoints
if FastAPI:
    app = FastAPI(title="Polymarket Bot Health Check API")

    health_checker = SystemHealthCheck()

    @app.get("/health", response_model=HealthStatus)
    async def get_health(environment: str = "production") -> Dict[str, Any]:
        """Get comprehensive health status"""
        return await health_checker.check_overall_health(environment)

    @app.get("/health/environment")
    async def get_environment_health(environment: str = "production") -> Dict[str, Any]:
        """Get environment-specific health"""
        env_health = health_checker.env_manager.validate_environment(environment)
        return {
            "environment": environment,
            "healthy": env_health.is_healthy,
            "details": {
                "python_version_ok": env_health.python_version_ok,
                "dependencies_ok": env_health.dependencies_ok,
                "configuration_ok": env_health.configuration_ok,
                "security_ok": env_health.security_ok,
            },
            "issues": env_health.issues,
            "timestamp": env_health.last_check,
        }

    @app.get("/health/dependencies")
    async def get_dependency_health(environment: str = "production") -> Dict[str, Any]:
        """Get dependency health status"""
        statuses = health_checker.dep_manager.get_dependency_status(environment)
        vulnerabilities = health_checker.dep_manager.check_vulnerabilities(environment)

        return {
            "environment": environment,
            "dependencies": [
                {
                    "name": s.name,
                    "installed": s.is_installed,
                    "version": s.current_version,
                    "required": s.required_version,
                }
                for s in statuses
            ],
            "vulnerabilities": len(vulnerabilities),
            "critical_missing": len(
                [
                    s
                    for s in statuses
                    if not s.is_installed
                    and any(
                        spec.security_critical
                        for spec in health_checker.dep_manager.dependencies.values()
                        if spec.name == s.name
                    )
                ]
            ),
        }

    @app.get("/health/reproducibility")
    async def get_reproducibility_status(
        environment: str = "production",
    ) -> Dict[str, Any]:
        """Check environment reproducibility"""
        return await health_checker.check_environment_reproduction(environment)


def main() -> int:
    """CLI interface for health checks"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Health Check System for Polymarket Copy Bot"
    )
    parser.add_argument("action", choices=["check", "serve", "reproduce"])
    parser.add_argument("--env", default="production", help="Environment name")
    parser.add_argument("--port", type=int, default=8000, help="Port for health API")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    checker = SystemHealthCheck()

    if args.action == "check":
        # Run synchronous health check
        async def run_check():
            health = await checker.check_overall_health(args.env)
            print(
                json.dumps(
                    {
                        "status": health.status,
                        "environment": health.environment,
                        "issues": health.issues,
                        "checks": health.checks,
                    },
                    indent=2,
                    default=str,
                )
            )

        asyncio.run(run_check())

    elif args.action == "serve":
        if not FastAPI:
            print("❌ FastAPI not available. Install with: pip install fastapi uvicorn")
            return 1

        print(f"🚀 Starting health check API on port {args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port)

    elif args.action == "reproduce":

        async def run_reproduce():
            result = await checker.check_environment_reproduction(args.env)
            print(json.dumps(result, indent=2))

        asyncio.run(run_reproduce())

    return 0


if __name__ == "__main__":
    sys.exit(main())
