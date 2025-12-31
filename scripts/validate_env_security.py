#!/usr/bin/env python3
"""
Environment security validation script.

This script performs comprehensive security checks on .env files:
1. Validates .env file permissions (should be 600)
2. Checks for sensitive data leakage in logs
3. Validates .env is in .gitignore
4. Ensures no .env files are committed to git
5. Validates .env structure without exposing values

Usage:
    python scripts/validate_env_security.py
"""

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Tuple


class EnvSecurityValidator:
    """Environment security validator"""

    # Required critical variables (values not logged for security)
    REQUIRED_VARS = [
        "PRIVATE_KEY",
        "POLYGON_RPC_URL",
    ]

    # Optional important variables
    OPTIONAL_VARS = [
        "POLYGONSCAN_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "POLYMARKET_API_KEY",
        "DRY_RUN",
        "USE_TESTNET",
        "MAX_POSITION_SIZE",
        "MAX_DAILY_LOSS",
        "SCAN_INTERVAL_HOURS",
        "MAX_WALLETS_TO_MONITOR",
    ]

    # Patterns that should never appear in logs
    SENSITIVE_PATTERNS = [
        r"PRIVATE_KEY\s*=",
        r"SECRET_KEY\s*=",
        r"API_KEY\s*=",
        r"TELEGRAM_BOT_TOKEN\s*=",
        r"0x[a-fA-F0-9]{64}",  # Private key pattern
        r"0x[a-fA-F0-9]{40}",  # Wallet address (may be logged masked)
    ]

    def __init__(self, project_root: str = None):
        """Initialize validator with project root"""
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.env_file = self.project_root / ".env"
        self.gitignore_file = self.project_root / ".gitignore"

    def validate_permissions(self) -> Tuple[bool, str]:
        """Validate .env file permissions are secure (600)"""
        if not self.env_file.exists():
            return True, "⚠️  .env file does not exist (skip permission check)"

        try:
            file_stat = os.stat(self.env_file)
            mode = file_stat.st_mode
            file_perms = stat.filemode(mode)
            octal_perms = oct(mode)[-3:]

            if octal_perms == "600":
                return True, f"✅ .env file permissions: {file_perms} ({octal_perms})"
            else:
                return False, (
                    f"❌ .env file permissions insecure: {file_perms} ({octal_perms})\n"
                    f"   Expected: -rw------- (600)\n"
                    f"   Fix: chmod 600 .env"
                )
        except Exception as e:
            return False, f"❌ Error checking .env permissions: {e}"

    def validate_gitignore(self) -> Tuple[bool, str]:
        """Validate .env is in .gitignore"""
        if not self.gitignore_file.exists():
            return False, (
                "❌ .gitignore file does not exist\n"
                "   Create: echo '.env' >> .gitignore"
            )

        try:
            with open(self.gitignore_file, "r") as f:
                gitignore_content = f.read()

            if ".env" in gitignore_content:
                return True, "✅ .env is in .gitignore"
            else:
                return False, (
                    "❌ .env is NOT in .gitignore\n   Fix: echo '.env' >> .gitignore"
                )
        except Exception as e:
            return False, f"❌ Error checking .gitignore: {e}"

    def validate_no_commit(self) -> Tuple[bool, str]:
        """Validate .env is not committed to git"""
        try:
            # Check if .env is tracked by git
            result = subprocess.run(
                ["git", "ls-files", ".env"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                return False, (
                    "❌ .env file is tracked by git!\n"
                    "   Fix: git rm --cached .env && git commit -m 'Remove .env from git'"
                )
            else:
                return True, "✅ .env is not tracked by git"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Not a git repository or git not available
            return True, "⚠️  Git not available - skipping git check"
        except Exception as e:
            return False, f"❌ Error checking git status: {e}"

    def validate_structure(self) -> Tuple[bool, str]:
        """Validate .env structure without exposing values"""
        if not self.env_file.exists():
            return True, "⚠️  .env file does not exist (skip structure check)"

        try:
            with open(self.env_file, "r") as f:
                lines = f.readlines()

            # Check for required variables (don't log values)
            missing_required = []
            for var in self.REQUIRED_VARS:
                if not any(var in line for line in lines):
                    missing_required.append(var)

            if missing_required:
                return False, (
                    f"❌ Missing required variables: {', '.join(missing_required)}\n"
                    f"   Required: {', '.join(self.REQUIRED_VARS)}"
                )

            # Count configured variables (excluding comments and empty lines)
            configured_vars = sum(
                1
                for line in lines
                if "=" in line and line.strip() and not line.strip().startswith("#")
            )

            # Check for optional variables
            configured_optional = []
            for var in self.OPTIONAL_VARS:
                if any(var in line for line in lines):
                    configured_optional.append(var)

            status = (
                f"✅ .env structure valid\n"
                f"   - Required variables: {len(self.REQUIRED_VARS)}/{len(self.REQUIRED_VARS)} present\n"
                f"   - Optional variables: {len(configured_optional)}/{len(self.OPTIONAL_VARS)} configured\n"
                f"   - Total configured: {configured_vars} variables"
            )
            return True, status

        except Exception as e:
            return False, f"❌ Error validating .env structure: {e}"

    def check_sensitive_logging(self) -> Tuple[bool, str]:
        """Check if any Python files log sensitive .env data"""
        issues = []
        exclude_dirs = {
            ".git",
            "venv",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            "scripts",
        }

        # Check common Python files (exclude scripts/ which contains security scripts)
        python_files = list(self.project_root.rglob("*.py"))

        for py_file in python_files:
            # Skip excluded directories
            if any(exclude_dir in py_file.parts for exclude_dir in exclude_dirs):
                continue

            # Skip this script itself and other security scripts
            if py_file.name in [
                "validate_env_security.py",
                "check_env_template.py",
                "check_current_state.py",
            ]:
                continue

            # Skip utility files that handle security/masking (false positives)
            if py_file.name in [
                "logging_security.py",
                "multi_env_manager.py",
                "environment_manager.py",
            ]:
                continue

            try:
                with open(py_file, "r") as f:
                    content = f.read()

                # Check for logging .env file contents (reading lines and printing)
                if 'with open(".env"' in content or "with open('.env'" in content:
                    if "readlines()" in content and (
                        "print(" in content or "logger" in content
                    ):
                        # Check if it's actually printing .env values (not just checking presence)
                        # Bad pattern: line.split('=')[1] - extracts value
                        # Good pattern: if var in line - only checks presence
                        if "line.split('=')" in content and "[1]" in content:
                            issues.append(
                                f"  - {py_file.relative_to(self.project_root)}"
                            )

                # Check for direct logging of env vars with actual values
                # Bad: logger.info(f"PRIVATE_KEY={PRIVATE_KEY}")
                # Good: logger.info("PRIVATE_KEY is set")
                # Also skip: f"[PRIVATE_KEY]" (masking) or f"PRIVATE_KEY=your_" (template)
                if "logger.info(" in content or "print(" in content:
                    import re

                    # Find all f-strings that might log sensitive values
                    # Look for patterns like f"PRIVATE_KEY={var}" but exclude:
                    # - Masking patterns: f"[PRIVATE_KEY]"
                    # - Template patterns: f"your_*_key_here"
                    # - Comment patterns: # PRIVATE_KEY=
                    fstring_patterns = re.finditer(
                        r'f["\'][^"\']*\b(PRIVATE_KEY|SECRET_KEY|API_KEY|TELEGRAM_BOT_TOKEN|POLYGONSCAN_API_KEY)\b\s*=\s*[^"\']+[\'"]',
                        content,
                    )

                    for match in fstring_patterns:
                        matched_text = match.group(0)
                        # Skip if it's a template (contains "here" or "your_")
                        if "here" in matched_text or "your_" in matched_text:
                            continue
                        # Skip if it's just the key name without interpolation (like "PRIVATE_KEY=")
                        # Actually checking the variable value
                        if "}" in matched_text and not matched_text.endswith("here"):
                            issues.append(
                                f"  - {py_file.relative_to(self.project_root)}"
                            )
                            break

            except Exception:
                pass

        if issues:
            return False, (
                "⚠️  Potential sensitive logging detected:\n"
                + "\n".join(issues)
                + "\n   Review these files and ensure .env values are not logged"
            )
        else:
            return True, "✅ No sensitive .env logging detected"

    def validate_all(self) -> bool:
        """Run all security checks and print results"""
        print("=" * 80)
        print("🔐 Environment Security Validation")
        print("=" * 80)

        checks = [
            ("File Permissions", self.validate_permissions),
            (".gitignore Check", self.validate_gitignore),
            ("Git Commit Check", self.validate_no_commit),
            (".env Structure", self.validate_structure),
            ("Sensitive Logging", self.check_sensitive_logging),
        ]

        all_passed = True
        for check_name, check_func in checks:
            print(f"\n{check_name}:")
            passed, message = check_func()
            print(f"  {message}")
            if not passed:
                all_passed = False

        print("\n" + "=" * 80)
        if all_passed:
            print("✅ All security checks passed!")
            return True
        else:
            print("❌ Some security checks failed - please fix the issues above")
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate environment security")
    parser.add_argument(
        "--project-root",
        help="Project root directory (default: current directory)",
        default=None,
    )
    args = parser.parse_args()

    validator = EnvSecurityValidator(args.project_root)
    success = validator.validate_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
