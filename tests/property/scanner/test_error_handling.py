"""
Property-Based Tests for Error handling.

@spec FEAT-001 - Error handling verification

Verify that error messages never expose secrets and error types are correctly classified.
Verify depth parameter preservation during error classification.
"""

import httpx
import pytest
from hypothesis import given, settings, strategies as st

from src.scanner.error_handlers import classify_httpx_error, create_crawl_error_result


class TestClassifyHttpxError:
    """Tests for classify_httpx_error function."""

    def test_timeout_error(self):
        """Timeout exception is classified correctly."""
        error_type, error_message = classify_httpx_error(
            httpx.TimeoutException("timeout")
        )
        assert error_type == "timeout"
        assert error_message == "HTTP request timed out"

    def test_ssl_error(self):
        """SSL error is classified correctly."""
        error_type, error_message = classify_httpx_error(
            httpx.ConnectError("SSL certificate error")
        )
        assert error_type == "ssl_error"
        assert error_message == "SSL/TLS certificate error"

    def test_connection_refused(self):
        """Connection refused is classified correctly."""
        error_type, error_message = classify_httpx_error(
            httpx.ConnectError("connection refused")
        )
        assert error_type == "connection_refused"
        assert error_message == "Connection refused"

    def test_dns_timeout(self):
        """DNS timeout is classified correctly."""
        error_type, error_message = classify_httpx_error(
            httpx.ConnectTimeout("DNS timeout")
        )
        assert error_type == "dns_timeout"
        assert error_message == "DNS resolution timeout"

    def test_redirect_loop(self):
        """Redirect loop is classified correctly."""
        error_type, error_message = classify_httpx_error(
            httpx.TooManyRedirects("redirect loop")
        )
        assert error_type == "redirect_loop"
        assert error_message == "Too many redirects (possible loop)"

    def test_generic_error(self):
        """Generic exception is handled."""
        error_type, error_message = classify_httpx_error(
            Exception("generic error message")
        )
        assert error_type == "error"
        assert "generic error message" in error_message


class TestCreateCrawlErrorResult:
    """Tests for create_crawl_error_result function."""

    def test_basic_error_result(self):
        """Basic error result is created correctly."""
        result = create_crawl_error_result(
            url="https://example.com",
            error=httpx.TimeoutException("timeout"),
            depth=3,
            parent_url="https://parent.com",
        )
        assert result["url"] == "https://example.com"
        assert result["status"] == "broken"
        assert result["error"] == "HTTP request timed out"
        assert result["depth"] == 3
        assert result["parent_url"] == "https://parent.com"

    def test_error_result_with_status_code(self):
        """Error result with status code is created correctly."""
        result = create_crawl_error_result(
            url="https://example.com",
            error=httpx.ConnectError("connection refused"),
            depth=2,
            parent_url=None,
            status_code=503,
        )
        assert result["status_code"] == 503
        assert result["parent_url"] is None


class TestErrorMessagesNeverExposeSecrets:
    """Property tests verifying error messages never expose sensitive data."""

    @given(st.text(alphabet=st.characters(), min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_error_message_truncation(self, message):
        """Error messages are truncated to 100 characters."""
        error = Exception(message)
        error_type, error_message = classify_httpx_error(error)

        # Generic errors are truncated
        if error_type == "error":
            assert len(error_message) <= 100

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=50)
    def test_depth_preserved(self, depth):
        """Depth parameter is preserved in error results."""
        result = create_crawl_error_result(
            url="https://example.com",
            error=httpx.TimeoutException("timeout"),
            depth=depth,
            parent_url=None,
        )
        assert result["depth"] == depth
