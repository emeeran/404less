"""
Async Crawler Module

@spec FEAT-001 - Core crawler engine

Async HTTP crawler with rate limiting, depth tracking, and error classification.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional, Set, List, Callable, Awaitable
from urllib.parse import urlparse, urljoin, urlunparse
from uuid import UUID

import httpx

from .robots import RobotsChecker


@dataclass
class CrawlResult:
    """
    Result of checking a single URL.

    @spec FEAT-001/DM-002
    """
    url: str
    status: str  # "ok", "broken", "skipped"
    status_code: Optional[int] = None
    error: Optional[str] = None
    depth: int = 0
    parent_url: Optional[str] = None
    content: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "status": self.status,
            "status_code": self.status_code,
            "error": self.error,
            "depth": self.depth,
            "parent_url": self.parent_url,
        }


class LinkExtractor(HTMLParser):
    """
    Extract links from HTML content.

    @spec FEAT-001 - Link extraction for recursive crawling
    """

    def __init__(self):
        super().__init__()
        self.links: Set[str] = set()

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        """Extract href/src attributes from relevant tags."""
        attr_map = {
            "a": "href",
            "img": "src",
            "link": "href",
            "script": "src",
            "iframe": "src",
            "source": "src",
            "track": "src",
            "embed": "src",
            "area": "href",
        }

        if tag in attr_map:
            target_attr = attr_map[tag]
            for attr, value in attrs:
                if attr == target_attr and value:
                    self.links.add(value)

    def get_links(self) -> Set[str]:
        """Return extracted links."""
        return self.links


@dataclass
class CrawlerConfig:
    """Configuration for the crawler."""
    max_concurrent: int = 5  # @spec FEAT-001/C-001
    min_delay: float = 0.1  # @spec FEAT-001/C-001 - 100ms minimum delay
    timeout: int = 30  # @spec FEAT-001 - 30 second timeout
    max_redirects: int = 10  # @spec FEAT-001/EC-001
    user_agent: str = "404less/0.1.0 (+https://github.com/user/404less)"  # @spec FEAT-001/C-006


class AsyncCrawler:
    """
    Async HTTP crawler with rate limiting and depth tracking.

    @spec FEAT-001/C-001 - Rate limiting (5 concurrent, 100ms delay)
    @spec FEAT-001/AC-003 - Recursive depth limiting
    @spec FEAT-001/AC-004 - Identify broken links
    @spec FEAT-001/AC-005 - Same-domain restriction
    """

    # @spec FEAT-001/EC-009 - Non-HTTP URL schemes to skip
    SKIPPED_SCHEMES = {"mailto:", "tel:", "javascript:", "ftp:", "file:", "data:"}

    def __init__(
        self,
        scan_id: UUID,
        config: Optional[CrawlerConfig] = None,
        robots_checker: Optional[RobotsChecker] = None,
        on_link_checked: Optional[Callable[[CrawlResult], Awaitable[None]]] = None,
        on_progress: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        """
        Initialize crawler.

        Args:
            scan_id: Scan ID for tracking
            config: Crawler configuration
            robots_checker: Robots.txt checker instance
            on_link_checked: Callback when a link is checked
            on_progress: Callback for progress updates
        """
        self.scan_id = scan_id
        self.config = config or CrawlerConfig()
        self.robots_checker = robots_checker
        self.on_link_checked = on_link_checked
        self.on_progress = on_progress

        # Rate limiting
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self.last_request_time: dict[str, float] = {}

        # State tracking
        self.visited: Set[str] = set()
        self.is_stopped = False
        self.current_url: Optional[str] = None

        # Statistics
        self.total_links = 0
        self.checked_links = 0
        self.broken_links = 0

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc

    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        """
        Normalize and resolve URL.

        @spec FEAT-001/EC-009 - Skip non-HTTP schemes
        @spec FEAT-001/C-004 - Sanitize URLs
        """
        # Skip non-HTTP schemes
        url_lower = url.lower()
        for scheme in self.SKIPPED_SCHEMES:
            if url_lower.startswith(scheme):
                return None

        # Resolve relative URLs
        resolved = urljoin(base_url, url)

        # Parse and normalize
        parsed = urlparse(resolved)

        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return None

        # Remove fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",  # Remove fragment
        ))

        # Sanitize for XSS prevention - escape dangerous characters
        # @spec FEAT-001/C-004
        normalized = re.sub(r'[<>"\']', '', normalized)

        return normalized

    async def _enforce_rate_limit(self, url: str) -> None:
        """
        Enforce rate limiting per domain.

        @spec FEAT-001/C-001 - 100ms minimum delay between requests to same domain
        """
        domain = self._get_domain(url)

        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.config.min_delay:
                await asyncio.sleep(self.config.min_delay - elapsed)

        self.last_request_time[domain] = time.time()

    async def check_url(
        self, url: str, depth: int, parent_url: Optional[str] = None
    ) -> CrawlResult:
        """
        Check single URL with rate limiting.

        @spec FEAT-001/AC-004 - Identify broken links
        @spec FEAT-001/EC-001 - Follow redirects up to 10 hops
        @spec FEAT-001/EC-010 - Distinguish error types
        """
        # Check if stopped
        if self.is_stopped:
            return CrawlResult(
                url=url, status="skipped", error="scan_stopped",
                depth=depth, parent_url=parent_url
            )

        # Check robots.txt
        if self.robots_checker:
            try:
                can_fetch = await self.robots_checker.can_fetch(
                    url, self.config.user_agent
                )
                if not can_fetch:
                    return CrawlResult(
                        url=url, status="skipped", error="robots_txt_disallowed",
                        depth=depth, parent_url=parent_url
                    )
            except Exception:
                pass  # Continue if robots.txt check fails

        self.current_url = url

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
                max_redirects=self.config.max_redirects,
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.config.user_agent},
                    follow_redirects=True,
                )

                status = "ok" if 200 <= response.status_code < 400 else "broken"

                return CrawlResult(
                    url=url,
                    status=status,
                    status_code=response.status_code,
                    depth=depth,
                    parent_url=parent_url,
                    content=response.text if status == "ok" else None,
                )

        except httpx.TimeoutException:
            # @spec FEAT-001/EC-010 - HTTP timeout
            return CrawlResult(
                url=url, status="broken", error="timeout",
                depth=depth, parent_url=parent_url
            )

        except httpx.ConnectError as e:
            # @spec FEAT-001/EC-010 - SSL and connection errors
            error_str = str(e).lower()
            if "ssl" in error_str or "certificate" in error_str:
                error = "ssl_error"
            else:
                error = "connection_refused"
            return CrawlResult(
                url=url, status="broken", error=error,
                depth=depth, parent_url=parent_url
            )

        except httpx.ConnectTimeout:
            # @spec FEAT-001/EC-010 - DNS timeout
            return CrawlResult(
                url=url, status="broken", error="dns_timeout",
                depth=depth, parent_url=parent_url
            )

        except httpx.TooManyRedirects:
            # @spec FEAT-001/EC-001 - Redirect loop
            return CrawlResult(
                url=url, status="broken", error="redirect_loop",
                depth=depth, parent_url=parent_url
            )

        except Exception as e:
            return CrawlResult(
                url=url, status="broken", error=str(e)[:100],
                depth=depth, parent_url=parent_url
            )

    def extract_links(self, html: str, base_url: str) -> Set[str]:
        """
        Extract and normalize links from HTML.

        @spec FEAT-001/C-004 - Sanitize URLs for XSS prevention
        @spec FEAT-001/EC-004 - Deduplicate URLs
        """
        extractor = LinkExtractor()
        try:
            extractor.feed(html)
        except Exception:
            return set()

        normalized_links: Set[str] = set()
        for link in extractor.get_links():
            normalized = self._normalize_url(link, base_url)
            if normalized:
                normalized_links.add(normalized)

        return normalized_links

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs are on the same domain.

        @spec FEAT-001/AC-005 - Same-domain restriction
        """
        return self._get_domain(url1) == self._get_domain(url2)

    async def crawl(
        self,
        start_url: str,
        max_depth: int,
        respect_robots: bool = True,
    ) -> None:
        """
        Main crawl loop using BFS for depth tracking.

        @spec FEAT-001/AC-003 - Recursive depth limiting
        @spec FEAT-001/AC-005 - Same-domain only for recursion
        """
        # @spec FEAT-001/EC-008 - Clamp depth to 1-10 range
        max_depth = max(1, min(max_depth, 10))

        queue: asyncio.Queue[tuple[str, int, Optional[str]]] = asyncio.Queue()
        await queue.put((start_url, 0, None))

        while not queue.empty() and not self.is_stopped:
            # Process in batches to allow for concurrent checks
            batch: List[tuple[str, int, Optional[str]]] = []
            while not queue.empty() and len(batch) < self.config.max_concurrent:
                try:
                    item = queue.get_nowait()
                    batch.append(item)
                except asyncio.QueueEmpty:
                    break

            if not batch:
                break

            # Check URLs concurrently with rate limiting
            tasks = []
            for url, depth, parent_url in batch:
                # @spec FEAT-001/EC-004 - Deduplicate URLs
                if url in self.visited:
                    continue
                self.visited.add(url)
                self.total_links += 1

                async def check_and_store(u: str, d: int, p: Optional[str]) -> Optional[CrawlResult]:
                    async with self.semaphore:
                        await self._enforce_rate_limit(u)
                        result = await self.check_url(u, d, p)
                        return result

                tasks.append(check_and_store(url, depth, parent_url))

            # Wait for batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception) or result is None:
                    continue

                # Update statistics
                self.checked_links += 1
                if result.status == "broken":
                    self.broken_links += 1

                # Notify callback
                if self.on_link_checked:
                    await self.on_link_checked(result)

                # Report progress
                if self.on_progress:
                    await self.on_progress({
                        "checked_links": self.checked_links,
                        "total_links": self.total_links,
                        "broken_links": self.broken_links,
                        "current_url": result.url,
                    })

                # Extract links for recursion
                if result.status == "ok" and result.content and result.depth < max_depth:
                    links = self.extract_links(result.content, result.url)

                    for link in links:
                        # @spec FEAT-001/AC-005 - Only crawl same-domain URLs
                        if self.is_same_domain(link, start_url):
                            if link not in self.visited:
                                await queue.put((link, result.depth + 1, result.url))

    def stop(self) -> None:
        """
        Stop the crawler.

        @spec FEAT-001/AC-007 - Stop in-progress scan
        """
        self.is_stopped = True
