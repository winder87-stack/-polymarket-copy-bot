#!/usr/bin/env python3
"""
Print Statement Fixer for Polymarket Copy Trading Bot

This script helps convert print() statements to proper logging.
It analyzes files and provides recommendations for logging improvements.
"""

import re
import ast
from pathlib import Path
from typing import List, Dict

# Core files to fix (as per Issue #23)
CORE_FILES = [
    "core/market_condition_analyzer.py",
    "core/composite_scoring_engine.py",
    "core/red_flag_detector.py",
    "core/wallet_quality_scorer.py",
    "core/wallet_behavior_monitor.py",
    "core/dynamic_position_sizer.py",
    "core/cross_market_arb.py",
    "core/market_maker_alerts.py",
]

# Mapping of print statement types to logging levels
LOG_LEVELS = {
    "DEBUG": "Used for detailed debugging information",
    "INFO": "Used for general informational messages",
    "WARNING": "Used for warning messages",
    "ERROR": "Used for error messages",
    "CRITICAL": "Used for critical error messages",
}


def analyze_print_statement(file_path: Path, node, line_num: int) -> Dict:
    """Analyze a print statement node and determine appropriate logging level."""
    # Get the source code for the print statement
    with open(file_path, "r") as f:
        lines = f.readlines()

    line_content = lines[line_num - 1].strip()

    # Analyze content to determine logging level
    if hasattr(ast, "unparse"):
        content = ast.unparse(node)
    else:
        content = str(node)

    log_level = "INFO"
    reason = ""

    # Heuristics for determining log level
    if any(
        keyword in content.lower()
        for keyword in ["error", "exception", "failed", "cannot"]
    ):
        log_level = "ERROR"
        reason = "Contains error-related keywords"
    elif any(keyword in content.lower() for keyword in ["warning", "warn"]):
        log_level = "WARNING"
        reason = "Contains warning-related keywords"
    elif any(keyword in content.lower() for keyword in ["debug", "trace"]):
        log_level = "DEBUG"
        reason = "Contains debug-related keywords"
    elif any(
        keyword in content.lower() for keyword in ["critical", "fatal", "emergency"]
    ):
        log_level = "CRITICAL"
        reason = "Contains critical-related keywords"
    else:
        log_level = "INFO"
        reason = "Default to INFO for general output"

    return {
        "line": line_num,
        "content": line_content,
        "suggested_level": log_level,
        "reason": reason,
    }


def find_print_statements(file_path: Path) -> List[Dict]:
    """Find all print statements in a Python file."""
    try:
        with open(file_path, "r") as f:
            source = f.read()

        tree = ast.parse(source)
        print_statements = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for print() function calls (Python 3)
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    print_statements.append(
                        analyze_print_statement(file_path, node, node.lineno)
                    )

        return print_statements

    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


def generate_logger_import() -> str:
    """Generate the logger import statement."""
    return "from loguru import logger\n\n"


def generate_logger_replacement(print_info: Dict, class_name: str = None) -> str:
    """Generate a logging statement to replace a print statement."""
    level = print_info["suggested_level"]
    content = print_info["content"]

    # Extract the message from print()
    # Simple heuristic: get everything inside print(...)
    match = re.search(r"print\((.*?)\)", content)
    if match:
        message = match.group(1)
    else:
        # Fallback to the whole line
        message = content

    # Generate the logging call
    if level == "DEBUG":
        return f"logger.debug({message})"
    elif level == "INFO":
        return f"logger.info({message})"
    elif level == "WARNING":
        return f"logger.warning({message})"
    elif level == "ERROR":
        return f"logger.error({message})"
    elif level == "CRITICAL":
        return f"logger.critical({message})"
    else:
        return f"logger.info({message})"


def fix_file(file_path: Path, dry_run: bool = True) -> bool:
    """Fix print statements in a file."""
    print(f"\n{'=' * 60}")
    print(f"Analyzing: {file_path}")
    print(f"{'=' * 60}")

    print_statements = find_print_statements(file_path)

    if not print_statements:
        print("✅ No print statements found")
        return True

    print(f"\nFound {len(print_statements)} print statement(s):")
    print("-" * 60)

    for i, stmt in enumerate(print_statements, 1):
        print(f"\n#{i} Line {stmt['line']}")
        print(f"  Current:  {stmt['content']}")
        print(f"  Suggest:  {generate_logger_replacement(stmt)}")
        print(f"  Level:    {stmt['suggested_level']} - {stmt['reason']}")

    if not dry_run:
        print(f"\n{'=' * 60}")
        # Auto-confirm in apply mode
        confirm = "yes"

        if confirm.lower() in ["yes", "y"]:
            # Read the file
            with open(file_path, "r") as f:
                lines = f.readlines()

            # Add logger import if not present
            needs_import = True
            for line in lines:
                if "from loguru import logger" in line:
                    needs_import = False
                    break

            if needs_import:
                # Find the best place to add import (after other imports)
                import_index = 0
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        import_index = i + 1
                    elif import_index > 0 and not (
                        line.startswith("import ")
                        or line.startswith("from ")
                        or line.strip() == ""
                    ):
                        break

                lines.insert(import_index, "\nfrom loguru import logger\n")
                print(f"✅ Added logger import at line {import_index + 1}")

            # Replace print statements
            changes_made = 0
            for stmt in print_statements:
                line_num = stmt["line"]
                # Adjust line number if we added an import
                if needs_import and line_num >= import_index:
                    line_num += 1

                original_line = lines[line_num - 1]
                replacement = generate_logger_replacement(stmt)

                # Preserve indentation
                indent = len(original_line) - len(original_line.lstrip())
                lines[line_num - 1] = " " * indent + replacement + "\n"
                changes_made += 1
                print(f"✅ Replaced print() at line {line_num}")

            # Write back
            with open(file_path, "w") as f:
                f.writelines(lines)

            print(f"\n✅ Successfully fixed {changes_made} print statement(s)")
            return True
        else:
            print("❌ Changes cancelled")
            return False
    else:
        print(f"\n{'=' * 60}")
        print("DRY RUN - No changes made")
        print("Run with --apply to apply changes")
        print("=" * 60)
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix print statements in production code"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes (default: dry run)"
    )
    parser.add_argument(
        "--file", type=str, help="Specific file to fix (default: all core files)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Fix all files in the project"
    )

    args = parser.parse_args()

    if args.file:
        files = [Path(args.file)]
    elif args.all:
        # Find all Python files
        files = list(Path(".").rglob("*.py"))
        # Exclude test files and venv
        files = [f for f in files if "test" not in str(f) and "venv" not in str(f)]
    else:
        # Default to core files
        files = [Path(f) for f in CORE_FILES]

    total_prints = 0
    files_with_prints = 0

    for file_path in files:
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        print_statements = find_print_statements(file_path)
        if print_statements:
            total_prints += len(print_statements)
            files_with_prints += 1
            fix_file(file_path, dry_run=not args.apply)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"Files analyzed: {len(files)}")
    print(f"Files with print statements: {files_with_prints}")
    print(f"Total print statements: {total_prints}")
    print("=" * 60)

    if args.apply:
        print("\n✅ Changes applied successfully!")
        print("💡 Run 'ruff check . --fix' and 'ruff format .' to clean up formatting")
    else:
        print("\n💡 Run with --apply to apply changes")


if __name__ == "__main__":
    main()
