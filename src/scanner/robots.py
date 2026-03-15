"""
Robots.txt Parser Module

@spec FEAT-001/EC-003 - robots.txt respect with override option

Parses and checks robots.txt for crawl permission.
"""

import time
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx


class RobotsChecker:
    """
    Parses and checks robots.txt for crawl permission.

    @spec FEAT-001/EC-003
    """

    def __init__(self, timeout: int = 10):
        """
        Initialize robots checker.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._cache: Dict[str, tuple[float, bool]] = {}  # domain -> (timestamp, allowed)
        self._cache_ttl = 300  # 5 minutes cache
        self._robots_cache: Dict[str, str] = {}  # domain -> robots.txt content

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def fetch_robots_txt(self, base_url: str) -> Optional[str]:
        """
        Fetch robots.txt content for a domain.

        @spec FEAT-001/EC-003
        """
        domain = self._get_domain(base_url)
        robots_url = f"{domain}/robots.txt"

        # Check cache
        if domain in self._robots_cache:
            return self._robots_cache[domain]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    content = response.text
                    self._robots_cache[domain] = content
                    return content
                return None
        except Exception:
            return None

    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        @spec FEAT-001/EC-003 - robots.txt disallows crawling behavior

        Args:
            url: URL to check
            user_agent: User agent string (default: "*" for all bots)

        Returns:
            True if allowed, False if disallowed
        """
        domain = self._get_domain(url)
        parsed_url = urlparse(url)
        path = parsed_url.path or "/"

        # Check cache
        cache_key = f"{domain}:{path}:{user_agent}"
        if cache_key in self._cache:
            timestamp, allowed = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return allowed

        # Fetch robots.txt
        robots_content = await self.fetch_robots_txt(domain)
        if not robots_content:
            # No robots.txt means everything is allowed
            return True

        # Parse robots.txt
        allowed = self._parse_robots(robots_content, path, user_agent)
        self._cache[cache_key] = (time.time(), allowed)

        return allowed

    def _parse_robots(self, content: str, path: str, user_agent: str) -> bool:
        """
        Parse robots.txt content and check path permission.

        Simple parser that handles basic Disallow/Allow directives.
        """
        lines = content.split("\n")
        current_user_agents: list[str] = []
        disallowed_paths: list[str] = []
        allowed_paths: list[str] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse directive
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if key == "user-agent":
                    current_user_agents = [value]
                elif key == "disallow" and self._matches_user_agent(
                    current_user_agents, user_agent
                ):
                    if value:
                        disallowed_paths.append(value)
                elif key == "allow" and self._matches_user_agent(
                    current_user_agents, user_agent
                ):
                    if value:
                        allowed_paths.append(value)

        # Check allow first (more specific)
        for allow_path in allowed_paths:
            if self._path_matches(path, allow_path):
                return True

        # Check disallow
        for disallow_path in disallowed_paths:
            if self._path_matches(path, disallow_path):
                return False

        return True

    def _matches_user_agent(self, patterns: list[str], user_agent: str) -> bool:
        """Check if user agent matches any pattern."""
        ua_lower = user_agent.lower()
        for pattern in patterns:
            pattern_lower = pattern.lower()
            if pattern_lower == "*" or pattern_lower in ua_lower or ua_lower in pattern_lower:
                return True
        return False

    def _path_matches(self, path: str, pattern: str) -> bool:
        """
        Check if path matches robots.txt pattern.

        Supports * (any characters) and $ (end anchor).
        """
        if pattern == "/":
            return path.startswith("/")

        # Convert robots.txt pattern to simple matching
        if pattern.endswith("*"):
            return path.startswith(pattern[:-1])
        elif pattern.endswith("$"):
            return path == pattern[:-1]
        else:
            return path.startswith(pattern)

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()
        self._robots_cache.clear()
