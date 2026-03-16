"""
Error Handlers Module

@spec FEAT-001 - Error classification for crawler

Extracts error handling logic from crawler to reduce complexity.
"""

from typing import Optional, Tuple
import httpx


def classify_httpx_error(error: Exception) -> Tuple[str, str]:
    """
    Classify httpx exceptions into error codes.

    Reduces cyclomatic complexity in check_url method.

    @spec FEAT-001/EC-010 - Distinguish error types

    """
    if isinstance(error, httpx.TimeoutException):
        return "timeout", "HTTP request timed out"

    if isinstance(error, httpx.ConnectError):
        error_str = str(error).lower()
        if "ssl" in error_str or "certificate" in error_str:
            return "ssl_error", "SSL/TLS certificate error"
        return "connection_refused", "Connection refused"

    if isinstance(error, httpx.ConnectTimeout):
        return "dns_timeout", "DNS resolution timeout"

    if isinstance(error, httpx.TooManyRedirects):
        return "redirect_loop", "Too many redirects (possible loop)"

    # Generic error - truncate to prevent log injection
    return "error", str(error)[:100]


def create_crawl_error_result(
    url: str,
    error: Exception,
    depth: int,
    parent_url: Optional[str],
    status_code: Optional[int] = None,
) -> dict:
    """
    Create a standardized error result dictionary.

    Args:
        url: URL that failed
        error: Exception that occurred
        depth: Crawl depth
        parent_url: Parent URL (for context)
        status_code: HTTP status code if available

    Returns:
        Dictionary suitable for CrawlResult
    """
    error_type, error_message = classify_httpx_error(error)

    return {
        "url": url,
        "status": "broken",
        "status_code": status_code,
        "error": error_message if error_type != "error" else error_type,
        "depth": depth,
        "parent_url": parent_url,
    }
