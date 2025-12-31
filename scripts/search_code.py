#!/usr/bin/env python3
"""
CLI script for codebase pattern searching.

This script provides a command-line interface for searching the Polymarket
Copy Bot codebase using the codebase_search MCP server.

Usage:
    python scripts/search_code.py --pattern money_calculations
    python scripts/search_code.py --pattern risk_controls --include-tests
    python scripts/search_code.py --custom "def.*trade" --directory core/
    python scripts/search_code.py --list-patterns
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.codebase_search import CodebaseSearchServer, SearchResult, get_search_server
from utils.logger import get_logger

logger = get_logger(__name__)


class SearchCodeCLI:
    """CLI interface for codebase searching."""

    def __init__(self):
        """Initialize CLI."""
        self.server: CodebaseSearchServer = None
        self.args = None

    def parse_args(self) -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Search Polymarket Copy Bot codebase for patterns",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Search for predefined pattern
  python scripts/search_code.py --pattern money_calculations

  # Search in specific directories
  python scripts/search_code.py --pattern risk_controls --directory core/ utils/

  # Include test files in search
  python scripts/search_code.py --pattern api_endpoints --include-tests

  # Custom regex search
  python scripts/search_code.py --custom "circuit_breaker.*is_tripped"

  # List available patterns
  python scripts/search_code.py --list-patterns

  # Get statistics
  python scripts/search_code.py --stats
            """,
        )

        # Search mode: predefined pattern or custom regex
        mode_group = parser.add_mutually_exclusive_group(required=False)
        mode_group.add_argument(
            "--pattern",
            type=str,
            help="Predefined pattern name to search for",
        )
        mode_group.add_argument(
            "--custom",
            type=str,
            help="Custom regex pattern to search for",
        )

        # Directory options
        parser.add_argument(
            "--directory",
            type=str,
            action="append",
            help="Directory to search (can be specified multiple times)",
        )
        parser.add_argument(
            "--include-tests",
            action="store_true",
            help="Include test files in search",
        )

        # Output options
        parser.add_argument(
            "--max-results",
            type=int,
            help="Maximum number of results to return (default: from config)",
        )
        parser.add_argument(
            "--output",
            choices=["text", "json", "compact"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--context",
            type=int,
            default=2,
            help="Number of context lines to show (default: 2)",
        )

        # Utility options
        parser.add_argument(
            "--list-patterns",
            action="store_true",
            help="List all available predefined patterns",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show search server statistics",
        )
        parser.add_argument(
            "--clear-cache",
            action="store_true",
            help="Clear search result cache",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable cache for this search",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging",
        )

        return parser.parse_args()

    async def run(self) -> int:
        """
        Run CLI command.

        Returns:
            Exit code (0 for success, non-zero for errors)
        """
        self.args = self.parse_args()

        # Configure logging
        if self.args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # Initialize server
        logger.info("Initializing codebase search server...")
        self.server = get_search_server()

        try:
            # Handle utility commands
            if self.args.list_patterns:
                return self.list_patterns()
            elif self.args.stats:
                return self.show_stats()
            elif self.args.clear_cache:
                return self.clear_cache()

            # Validate search arguments
            if not self.args.pattern and not self.args.custom:
                print("Error: Must specify --pattern or --custom")
                print("\nUse --help for usage information")
                return 1

            # Perform search
            return await self.perform_search()

        except KeyboardInterrupt:
            print("\nSearch interrupted by user")
            return 130
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return 1
        finally:
            if self.server:
                await self.server.shutdown()

    async def perform_search(self) -> int:
        """
        Perform codebase search based on arguments.

        Returns:
            Exit code
        """
        try:
            if self.args.pattern:
                results = await self.server.search_pattern(
                    pattern_name=self.args.pattern,
                    target_directories=self.args.directory,
                    include_tests=self.args.include_tests,
                    max_results=self.args.max_results,
                    use_cache=not self.args.no_cache,
                )
            else:  # custom pattern
                results = await self.server.search_custom_pattern(
                    regex_pattern=self.args.custom,
                    target_directories=self.args.directory,
                    include_tests=self.args.include_tests,
                    max_results=self.args.max_results,
                )

            # Display results
            self.display_results(results)

            return 0

        except ValueError as e:
            print(f"Error: {e}")
            return 1
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1

    def display_results(self, results: List[SearchResult]) -> None:
        """
        Display search results based on output format.

        Args:
            results: List of search results
        """
        if not results:
            print("\nNo results found.")
            return

        if self.args.output == "json":
            self.display_json(results)
        elif self.args.output == "compact":
            self.display_compact(results)
        else:  # text
            self.display_text(results)

    def display_text(self, results: List[SearchResult]) -> None:
        """
        Display results in text format.

        Args:
            results: List of search results
        """
        print(f"\nFound {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result.file_path}:{result.line_number}")
            print(f"   Pattern: {result.pattern_name}")
            print(f"   Matched: {result.matched_text}")

            # Show context
            context_lines = self.args.context
            if result.context_before:
                print("\n   Context before:")
                for line in result.context_before[-context_lines:]:
                    print(f"     {line.rstrip()}")

            print(f"\n   Line: {result.line_content.strip()}")

            if result.context_after:
                print("\n   Context after:")
                for line in result.context_after[:context_lines]:
                    print(f"     {line.rstrip()}")

            print()

    def display_compact(self, results: List[SearchResult]) -> None:
        """
        Display results in compact format.

        Args:
            results: List of search results
        """
        print(f"\nFound {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            relative_path = Path(result.file_path).relative_to(Path.cwd())
            print(
                f"{i:3d}. {relative_path}:{result.line_number:4d} - {result.matched_text[:60]}"
            )

    def display_json(self, results: List[SearchResult]) -> None:
        """
        Display results in JSON format.

        Args:
            results: List of search results
        """
        output = {
            "count": len(results),
            "results": [result.to_dict() for result in results],
        }

        print(json.dumps(output, indent=2, sort_keys=True))

    def list_patterns(self) -> int:
        """
        List all available search patterns.

        Returns:
            Exit code
        """
        patterns = self.server.list_patterns()

        if self.args.output == "json":
            print(json.dumps(patterns, indent=2, sort_keys=True))
        else:
            print("\nAvailable search patterns:\n")

            # Group by category
            by_category: Dict[str, List[Dict[str, Any]]] = {}
            for name, info in patterns.items():
                category = info.get("category", "general")
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append({"name": name, **info})

            # Display by category
            for category, pattern_list in sorted(by_category.items()):
                print(f"\n{category.upper()}:")

                for info in sorted(pattern_list, key=lambda x: x["name"]):
                    severity_icon = {
                        "info": "ℹ️",
                        "warning": "⚠️",
                        "error": "❌",
                    }.get(info["severity"], "📝")

                    print(f"  {severity_icon} {info['name']}")
                    print(f"     Pattern: {info['pattern']}")
                    print(f"     Description: {info['description']}")
                    print()

        return 0

    def show_stats(self) -> int:
        """
        Show search server statistics.

        Returns:
            Exit code
        """
        stats = self.server.get_stats()

        if self.args.output == "json":
            print(json.dumps(stats, indent=2, sort_keys=True))
        else:
            print("\nCodebase Search Server Statistics:\n")

            print(f"Searches performed: {stats['search_count']}")
            print(f"Cache hits: {stats['cache_hits']}")
            print(f"Cache misses: {stats['cache_misses']}")
            print(f"Cache hit ratio: {stats['cache_hit_ratio']:.1%}")
            print(f"Cache size: {stats['cache_size']} entries")
            print(f"Circuit breaker state: {stats['circuit_breaker_state']}")
            print(f"Circuit breaker failures: {stats['circuit_breaker_failures']}")
            print(f"Rate limiter requests: {stats['rate_limiter_requests']}")

            # Cache stats
            cache_stats = self.server.cache.get_stats()
            print("\nCache details:")
            print(f"  Max size: {cache_stats['max_size']}")
            print(f"  TTL: {cache_stats['ttl_seconds']}s")
            print(f"  Evictions: {cache_stats['evictions']}")
            print(f"  Estimated memory: {cache_stats['estimated_memory_mb']} MB")

        return 0

    def clear_cache(self) -> int:
        """
        Clear search result cache.

        Returns:
            Exit code
        """
        self.server.clear_cache()
        print("Search cache cleared")
        return 0


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    cli = SearchCodeCLI()
    return asyncio.run(cli.run())


if __name__ == "__main__":
    sys.exit(main())
