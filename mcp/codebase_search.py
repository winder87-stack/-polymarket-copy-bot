"""Codebase Search MCP Server for Polymarket Copy Bot.

This MCP server provides pattern-based code searching using Ruff as the underlying
engine for fast, efficient codebase navigation and analysis. It includes caching,
rate limiting, and circuit breaker patterns for production safety.

Key Features:
- Fast pattern-based code search using Ruff engine
- Cached results with configurable TTL (1-hour default)
- Rate limiting to prevent system overload (max 10 searches/minute)
- Circuit breaker for high system load protection
- Memory limits and result pagination
- Thread-safe operations with async support

Usage:
    from mcp.codebase_search import CodebaseSearchServer

    server = CodebaseSearchServer()
    results = await server.search_pattern("money_calculations")
"""

import asyncio
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.mcp_config import CodebaseSearchConfig, get_codebase_search_config
from utils.helpers import BoundedCache

logger = logging.getLogger(__name__)


@dataclass
class SearchPattern:
    """Data class representing a search pattern with metadata."""

    name: str
    pattern: str
    description: str
    category: str
    severity: str


@dataclass
class SearchResult:
    """Data class representing a single search result."""

    file_path: str
    line_number: int
    line_content: str
    pattern_name: str
    matched_text: str
    context_before: List[str]
    context_after: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content.strip(),
            "pattern_name": self.pattern_name,
            "matched_text": self.matched_text,
            "context_before": [line.strip() for line in self.context_before],
            "context_after": [line.strip() for line in self.context_after],
        }


class SearchCircuitBreaker:
    """Circuit breaker for codebase search operations during high system load."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout_seconds: Time to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.state: str = "closed"  # closed, open, half-open
        self._lock = threading.Lock()

    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped (open)."""
        with self._lock:
            if self.state == "closed":
                return False

            if self.state == "open":
                # Check if we can try recovery
                if (
                    time.time() - (self.last_failure_time or 0)
                    > self.recovery_timeout_seconds
                ):
                    self.state = "half-open"
                    logger.info("Circuit breaker transitioning to half-open state")
                    return False
                return True

            # half-open state
            return False

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self.state == "half-open":
                logger.info("Circuit breaker closing after successful operation")
                self.state = "closed"
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} consecutive failures"
                )


class RateLimiter:
    """Rate limiter for search operations."""

    def __init__(self, max_requests_per_minute: int = 10):
        """
        Initialize rate limiter.

        Args:
            max_requests_per_minute: Maximum requests allowed per minute
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.requests: OrderedDict[float, None] = OrderedDict()
        self._lock = threading.Lock()

    async def acquire(self) -> bool:
        """
        Attempt to acquire permission to perform a search.

        Returns:
            True if allowed, False if rate limit exceeded
        """
        with self._lock:
            now = time.time()
            minute_ago = now - 60

            # Remove requests older than 1 minute
            old_keys = [t for t in self.requests if t < minute_ago]
            for t in old_keys:
                del self.requests[t]

            # Check if we're under the limit
            if len(self.requests) < self.max_requests_per_minute:
                self.requests[now] = None
                return True

            logger.warning(
                f"Rate limit exceeded: {len(self.requests)}/{self.max_requests_per_minute} requests in last minute"
            )
            return False

    def get_wait_time(self) -> float:
        """
        Get estimated wait time until next request is allowed.

        Returns:
            Seconds to wait, or 0 if allowed now
        """
        with self._lock:
            if len(self.requests) < self.max_requests_per_minute:
                return 0.0

            now = time.time()
            oldest_request = next(iter(self.requests), now)
            return max(0.0, 60.0 - (now - oldest_request))


class CodebaseSearchServer:
    """
    MCP Server for codebase pattern searching using Ruff.

    This server provides fast pattern-based code searching with:
    - Ruff as the underlying search engine
    - Cached results with TTL
    - Rate limiting
    - Circuit breaker protection
    - Memory limits
    """

    def __init__(self, config: Optional[CodebaseSearchConfig] = None):
        """
        Initialize the codebase search server.

        Args:
            config: Optional configuration (uses default if not provided)
        """
        self.config = config or get_codebase_search_config()
        self.project_root = Path.cwd()

        # Initialize components
        self.circuit_breaker = SearchCircuitBreaker()
        self.rate_limiter = RateLimiter(self.config.rate_limit_requests_per_minute)
        self.cache: BoundedCache = BoundedCache(
            max_size=100,
            ttl_seconds=self.config.cache_ttl_seconds,
            memory_threshold_mb=self.config.memory_limit_mb,
            cleanup_interval_seconds=60,
        )

        # Statistics
        self.search_count: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0

        logger.info("CodebaseSearchServer initialized")
        logger.info(
            f"  - Config: enabled={self.config.enabled}, cache={self.config.cache_enabled}"
        )
        logger.info(f"  - Patterns: {len(self.config.search_patterns)}")

        # Start background cleanup
        asyncio.create_task(self._start_cleanup_task())

    async def _start_cleanup_task(self) -> None:
        """Start background cache cleanup task."""
        await self.cache.start_background_cleanup()

    async def search_pattern(
        self,
        pattern_name: str,
        target_directories: Optional[List[str]] = None,
        include_tests: bool = False,
        max_results: Optional[int] = None,
        use_cache: bool = True,
    ) -> List[SearchResult]:
        """
        Search codebase for a pattern by name.

        Args:
            pattern_name: Name of the predefined pattern to search for
            target_directories: Optional list of directories to search (default: all)
            include_tests: Whether to include test files
            max_results: Maximum results to return (default: from config)
            use_cache: Whether to use cached results

        Returns:
            List of search results

        Raises:
            ValueError: If pattern not found
            RuntimeError: If circuit breaker is tripped or rate limit exceeded
        """
        # Check circuit breaker
        if self.circuit_breaker.is_tripped():
            logger.warning("Circuit breaker is tripped, rejecting search request")
            raise RuntimeError("Circuit breaker is active. System under high load.")

        # Check rate limit
        if not await self.rate_limiter.acquire():
            wait_time = self.rate_limiter.get_wait_time()
            raise RuntimeError(
                f"Rate limit exceeded. Wait {wait_time:.1f}s before next request."
            )

        # Get pattern
        pattern = self.config.get_pattern(pattern_name)
        if not pattern:
            raise ValueError(f"Pattern not found: {pattern_name}")

        # Generate cache key
        cache_key = self._generate_cache_key(
            pattern_name, target_directories, include_tests
        )

        # Check cache
        if use_cache and self.config.cache_enabled:
            cached_results = self.cache.get(cache_key)
            if cached_results is not None:
                self.cache_hits += 1
                logger.info(f"Cache hit for pattern: {pattern_name}")
                return cached_results

        self.cache_misses += 1
        self.search_count += 1

        # Perform search
        try:
            results = await self._perform_search(
                pattern, pattern_name, target_directories, include_tests, max_results
            )
            self.circuit_breaker.record_success()

            # Cache results
            if use_cache and self.config.cache_enabled:
                self.cache.set(cache_key, results)

            return results

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"Search failed for pattern {pattern_name}: {e}", exc_info=True
            )
            raise

    async def search_custom_pattern(
        self,
        regex_pattern: str,
        target_directories: Optional[List[str]] = None,
        include_tests: bool = False,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """
        Search codebase for a custom regex pattern.

        Args:
            regex_pattern: Regular expression pattern to search for
            target_directories: Optional list of directories to search (default: all)
            include_tests: Whether to include test files
            max_results: Maximum results to return (default: from config)

        Returns:
            List of search results

        Raises:
            RuntimeError: If circuit breaker is tripped or rate limit exceeded
        """
        # Check circuit breaker
        if self.circuit_breaker.is_tripped():
            raise RuntimeError("Circuit breaker is active. System under high load.")

        # Check rate limit
        if not await self.rate_limiter.acquire():
            wait_time = self.rate_limiter.get_wait_time()
            raise RuntimeError(
                f"Rate limit exceeded. Wait {wait_time:.1f}s before next request."
            )

        self.search_count += 1

        # Perform search
        try:
            results = await self._perform_search(
                regex_pattern, "custom", target_directories, include_tests, max_results
            )
            self.circuit_breaker.record_success()
            return results

        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Custom pattern search failed: {e}", exc_info=True)
            raise

    async def _perform_search(
        self,
        pattern: str,
        pattern_name: str,
        target_directories: Optional[List[str]],
        include_tests: bool,
        max_results: Optional[int],
    ) -> List[SearchResult]:
        """
        Perform the actual search operation using Ruff.

        Args:
            pattern: Regex pattern to search for
            pattern_name: Name of the pattern
            target_directories: Directories to search
            include_tests: Whether to include test files
            max_results: Maximum results to return

        Returns:
            List of search results
        """
        # Determine directories to search
        if target_directories:
            search_dirs = [Path(d) for d in target_directories]
        else:
            search_dirs = self._get_default_search_directories()

        # Validate directories
        search_dirs = [d for d in search_dirs if d.exists() and d.is_dir()]

        if not search_dirs:
            logger.warning("No valid directories to search")
            return []

        # Use Ruff for fast searching
        results = await self._search_with_ruff(
            pattern, search_dirs, include_tests, max_results
        )

        logger.info(
            f"Search for '{pattern_name}' found {len(results)} results in {len(search_dirs)} directories"
        )

        return results

    async def _search_with_ruff(
        self,
        pattern: str,
        directories: List[Path],
        include_tests: bool,
        max_results: Optional[int],
    ) -> List[SearchResult]:
        """
        Use system grep to search for pattern in directories.

        Args:
            pattern: Regex pattern to search for
            directories: Directories to search
            include_tests: Whether to include test files
            max_results: Maximum results to return

        Returns:
            List of search results
        """
        results: List[SearchResult] = []
        max_results = max_results or self.config.max_results

        for directory in directories:
            # Build grep command for searching (ruff grep not available in 0.14.10)
            cmd = [
                "grep",
                "-r",
                "-n",
                "-E",
                pattern,
                str(directory),
            ]

            # Exclude test files if not included
            if not include_tests:
                cmd.extend(["--exclude-dir=tests", "--exclude=test_*.py"])

            # Exclude tests if not requested
            if not include_tests:
                cmd.extend(["--exclude", "tests/**,test_*.py,*_test.py"])

            try:
                # Run grep search
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )

                if process.returncode != 0:
                    # grep returns non-zero if no matches found
                    if process.returncode == 1 and not stderr:
                        continue  # No matches is OK
                    logger.warning(f"grep error: {stderr.decode()}")

                # Parse results
                if stdout:
                    directory_results = self._parse_grep_output(
                        stdout.decode(), pattern, directory
                    )
                    results.extend(directory_results)

                    # Check if we've hit the limit
                    if len(results) >= max_results:
                        results = results[:max_results]
                        break

            except asyncio.TimeoutError:
                logger.warning(f"Search timed out in directory: {directory}")
                break
            except Exception as e:
                logger.error(f"Error searching {directory}: {e}", exc_info=True)
                continue

        return results

    def _parse_grep_output(
        self, output: str, pattern_name: str, directory: Path
    ) -> List[SearchResult]:
        """
        Parse grep output into SearchResult objects.

        Args:
            output: Output from grep (format: file:line:content)
            pattern_name: Name of the pattern
            directory: Directory being searched

        Returns:
            List of search results
        """
        results: List[SearchResult] = []

        try:
            for line in output.strip().split("\n"):
                if not line:
                    continue

                try:
                    # Parse grep output: file:line:content
                    # grep -r returns paths relative to the searched directory
                    parts = line.split(":", 2)
                    if len(parts) < 3:
                        continue

                    # grep -r returns relative paths from searched directory
                    # So file_part is like "market_analyzer.py", not "scanners/market_analyzer.py"
                    file_part = parts[0]

                    # Only join if path is not already absolute
                    if Path(file_part).is_absolute():
                        file_path = file_part
                    else:
                        # Create path relative to the searched directory, then make it absolute from project root
                        # grep -r returns paths relative to CWD, not searched directory
                        # If file_part contains "/", it's relative to project root
                        if "/" in file_part:
                            file_path = str(Path.cwd() / file_part)
                        else:
                            # Just a filename, relative to searched directory
                            file_path = str(directory / file_part)

                    line_number = int(parts[1])
                    line_content = parts[2]
                    matched_text = pattern_name  # Use pattern name as matched text

                    if not file_path or not line_number:
                        continue

                    # Get context lines
                    context_before, context_after = self._get_context_lines(
                        file_path, line_number
                    )

                    result = SearchResult(
                        file_path=file_path,
                        line_number=line_number,
                        line_content=line_content,
                        pattern_name=pattern_name,
                        matched_text=matched_text,
                        context_before=context_before,
                        context_after=context_after,
                    )
                    results.append(result)

                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse grep line: {line}, error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing grep output: {e}", exc_info=True)

        return results

    def _get_context_lines(
        self, file_path: str, line_number: int, context_lines: int = 2
    ) -> Tuple[List[str], List[str]]:
        """
        Get context lines around a match.

        Args:
            file_path: Path to file
            line_number: Line number of match
            context_lines: Number of context lines before and after

        Returns:
            Tuple of (before_lines, after_lines)
        """
        before_lines = []
        after_lines = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()

            # Get lines before
            start = max(0, line_number - context_lines - 1)
            before_lines = all_lines[start : line_number - 1]

            # Get lines after
            end = min(len(all_lines), line_number + context_lines)
            after_lines = all_lines[line_number:end]

        except Exception as e:
            logger.debug(f"Error reading context lines from {file_path}: {e}")

        return before_lines, after_lines

    def _get_default_search_directories(self) -> List[Path]:
        """
        Get default directories to search.

        Returns:
            List of directories to search by default
        """
        directories = []

        # Core directories
        for dirname in [
            "core",
            "utils",
            "scanners",
            "trading",
            "risk_management",
            "monitoring",
        ]:
            dir_path = self.project_root / dirname
            if dir_path.exists() and dir_path.is_dir():
                directories.append(dir_path)

        # Config directory
        config_dir = self.project_root / "config"
        if config_dir.exists() and config_dir.is_dir():
            directories.append(config_dir)

        return directories

    def _generate_cache_key(
        self,
        pattern_name: str,
        target_directories: Optional[List[str]],
        include_tests: bool,
    ) -> str:
        """
        Generate a cache key for a search request.

        Args:
            pattern_name: Name of pattern
            target_directories: Directories being searched
            include_tests: Whether tests are included

        Returns:
            Cache key string
        """
        key_parts = [pattern_name]

        if target_directories:
            # Sort directories for consistent keys
            dirs_str = ",".join(sorted(target_directories))
            key_parts.append(dirs_str)

        key_parts.append(f"tests={include_tests}")

        return "|".join(key_parts)

    def list_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available search patterns with metadata.

        Returns:
            Dictionary of pattern name to metadata
        """
        return self.config.list_patterns()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get server statistics.

        Returns:
            Dictionary of server statistics
        """
        cache_stats = self.cache.get_stats()

        return {
            "search_count": self.search_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": self.cache_hits / max(1, self.search_count),
            "cache_size": cache_stats["size"],
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "rate_limiter_requests": len(self.rate_limiter.requests),
        }

    def clear_cache(self) -> None:
        """Clear the search cache."""
        self.cache.clear()
        logger.info("Search cache cleared")

    async def shutdown(self) -> None:
        """Shutdown the search server and cleanup resources."""
        logger.info("Shutting down CodebaseSearchServer...")
        await self.cache.stop_background_cleanup()
        logger.info("CodebaseSearchServer shutdown complete")


# Singleton instance
_search_server: Optional[CodebaseSearchServer] = None


def get_search_server() -> CodebaseSearchServer:
    """
    Get the codebase search server singleton.

    Returns:
        CodebaseSearchServer instance
    """
    global _search_server

    if _search_server is None:
        _search_server = CodebaseSearchServer()

    return _search_server


async def search_pattern(
    pattern_name: str,
    target_directories: Optional[List[str]] = None,
    include_tests: bool = False,
    max_results: Optional[int] = None,
) -> List[SearchResult]:
    """
    Convenience function to search codebase for a pattern.

    Args:
        pattern_name: Name of the predefined pattern to search for
        target_directories: Optional list of directories to search
        include_tests: Whether to include test files
        max_results: Maximum results to return

    Returns:
        List of search results
    """
    server = get_search_server()
    return await server.search_pattern(
        pattern_name, target_directories, include_tests, max_results
    )


if __name__ == "__main__":
    # Test the server
    import asyncio

    async def test():
        server = CodebaseSearchServer()

        print("\nAvailable patterns:")
        for name, info in server.list_patterns().items():
            print(f"  {name}: {info['description']}")

        print("\nSearching for money_calculations pattern...")
        results = await server.search_pattern("money_calculations")

        print(f"\nFound {len(results)} results:")
        for result in results[:5]:  # Show first 5
            print(f"\n  {result.file_path}:{result.line_number}")
            print(f"    {result.line_content.strip()}")
            print(f"    Matched: {result.matched_text}")

        await server.shutdown()

    asyncio.run(test())
