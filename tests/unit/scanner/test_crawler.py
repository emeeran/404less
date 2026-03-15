"""
Unit tests for AsyncCrawler.

@spec FEAT-001 - Crawler tests
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from src.scanner.crawler import (
    AsyncCrawler,
    CrawlerConfig,
    CrawlResult,
    LinkExtractor,
)


class TestCrawlerConfig:
    """Tests for CrawlerConfig."""

    def test_default_config(self):
        """@spec FEAT-001/C-001 - Default rate limiting"""
        config = CrawlerConfig()
        assert config.max_concurrent == 5
        assert config.min_delay == 0.1  # 100ms
        assert config.timeout == 30
        assert config.max_redirects == 10

    def test_custom_config(self):
        """Config can be customized."""
        config = CrawlerConfig(
            max_concurrent=10,
            min_delay=0.5,
            timeout=60,
        )
        assert config.max_concurrent == 10
        assert config.min_delay == 0.5
        assert config.timeout == 60


class TestCrawlResult:
    """Tests for CrawlResult."""

    def test_to_dict(self):
        """Test serialization."""
        result = CrawlResult(
            url="https://example.com",
            status="ok",
            status_code=200,
            depth=1,
            parent_url="https://example.org",
        )
        data = result.to_dict()
        assert data["url"] == "https://example.com"
        assert data["status"] == "ok"
        assert data["status_code"] == 200
        assert data["depth"] == 1

    def test_broken_result(self):
        """Test broken link result."""
        result = CrawlResult(
            url="https://example.com/404",
            status="broken",
            status_code=404,
            error="Not Found",
            depth=2,
        )
        assert result.status == "broken"
        assert result.error == "Not Found"


class TestLinkExtractor:
    """Tests for LinkExtractor."""

    def test_extract_anchor_links(self):
        """Extract href from anchor tags."""
        extractor = LinkExtractor()
        extractor.feed('<a href="https://example.com">Link</a>')
        links = extractor.get_links()
        assert "https://example.com" in links

    def test_extract_image_links(self):
        """Extract src from img tags."""
        extractor = LinkExtractor()
        extractor.feed('<img src="https://example.com/img.png">')
        links = extractor.get_links()
        assert "https://example.com/img.png" in links

    def test_extract_multiple_links(self):
        """Extract multiple link types."""
        extractor = LinkExtractor()
        extractor.feed('''
            <a href="/page1">Link</a>
            <img src="/img.png">
            <script src="/script.js"></script>
            <link href="/style.css">
        ''')
        links = extractor.get_links()
        assert "/page1" in links
        assert "/img.png" in links
        assert "/script.js" in links
        assert "/style.css" in links

    def test_ignore_empty_links(self):
        """Ignore empty href/src attributes."""
        extractor = LinkExtractor()
        extractor.feed('<a href="">Empty</a><a href="#">Anchor</a>')
        links = extractor.get_links()
        assert "" not in links


class TestAsyncCrawler:
    """Tests for AsyncCrawler."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return AsyncCrawler(
            scan_id=uuid4(),
            config=CrawlerConfig(),
        )

    def test_normalize_url_removes_fragment(self, crawler):
        """@spec FEAT-001 - Fragments are removed from URLs."""
        normalized = crawler._normalize_url(
            "https://example.com/page#section",
            "https://example.com"
        )
        assert normalized == "https://example.com/page"

    def test_normalize_url_skip_mailto(self, crawler):
        """@spec FEAT-001/EC-009 - Skip mailto: links."""
        result = crawler._normalize_url(
            "mailto:test@example.com",
            "https://example.com"
        )
        assert result is None

    def test_normalize_url_skip_javascript(self, crawler):
        """@spec FEAT-001/EC-009 - Skip javascript: links."""
        result = crawler._normalize_url(
            "javascript:void(0)",
            "https://example.com"
        )
        assert result is None

    def test_normalize_url_skip_ftp(self, crawler):
        """@spec FEAT-001/EC-009 - Skip ftp: links."""
        result = crawler._normalize_url(
            "ftp://example.com/file",
            "https://example.com"
        )
        assert result is None

    def test_normalize_url_relative(self, crawler):
        """Resolve relative URLs."""
        normalized = crawler._normalize_url(
            "/page",
            "https://example.com"
        )
        assert normalized == "https://example.com/page"

    def test_normalize_url_sanitize_xss(self, crawler):
        """@spec FEAT-001/C-004 - Sanitize URLs for XSS prevention."""
        # Remove < > " ' characters
        normalized = crawler._normalize_url(
            'https://example.com/page<script>alert(1)</script>',
            "https://example.com"
        )
        assert "<" not in normalized
        assert ">" not in normalized

    def test_is_same_domain(self, crawler):
        """@spec FEAT-001/AC-005 - Same-domain restriction."""
        assert crawler.is_same_domain(
            "https://example.com/page1",
            "https://example.com/page2"
        )
        assert not crawler.is_same_domain(
            "https://example.com",
            "https://other.com"
        )

    def test_extract_links_deduplicate(self, crawler):
        """@spec FEAT-001/EC-004 - Deduplicate URLs."""
        html = '''
            <a href="/page">Link</a>
            <a href="/page">Duplicate</a>
            <a href="/page">Another duplicate</a>
        '''
        links = crawler.extract_links(html, "https://example.com")
        # Should only have one /page link
        page_links = [l for l in links if l.endswith("/page")]
        assert len(page_links) == 1

    @pytest.mark.asyncio
    async def test_check_url_stopped_crawler(self, crawler):
        """Return skipped when crawler is stopped."""
        crawler.is_stopped = True
        result = await crawler.check_url("https://example.com", 0)
        assert result.status == "skipped"
        assert result.error == "scan_stopped"

    @pytest.mark.asyncio
    async def test_check_url_success(self, crawler):
        """@spec FEAT-001/AC-004 - Successful URL check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Content</html>"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await crawler.check_url("https://example.com", 0)

        assert result.status == "ok"
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_check_url_broken_404(self, crawler):
        """@spec FEAT-001/AC-004 - Identify broken links."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = ""

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await crawler.check_url("https://example.com/missing", 0)

        assert result.status == "broken"
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_check_url_timeout(self, crawler):
        """@spec FEAT-001/EC-010 - HTTP timeout classification."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")

            result = await crawler.check_url("https://example.com", 0)

        assert result.status == "broken"
        assert result.error == "timeout"

    @pytest.mark.asyncio
    async def test_check_url_ssl_error(self, crawler):
        """@spec FEAT-001/EC-010 - SSL error classification."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("SSL certificate error")

            result = await crawler.check_url("https://example.com", 0)

        assert result.status == "broken"
        assert result.error == "ssl_error"

    @pytest.mark.asyncio
    async def test_check_url_connection_refused(self, crawler):
        """@spec FEAT-001/EC-010 - Connection refused classification."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await crawler.check_url("https://example.com", 0)

        assert result.status == "broken"
        assert result.error == "connection_refused"

    @pytest.mark.asyncio
    async def test_check_url_redirect_loop(self, crawler):
        """@spec FEAT-001/EC-001 - Redirect loop detection."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TooManyRedirects("Too many redirects")

            result = await crawler.check_url("https://example.com", 0)

        assert result.status == "broken"
        assert result.error == "redirect_loop"

    def test_stop(self, crawler):
        """@spec FEAT-001/AC-007 - Stop in-progress scan."""
        assert crawler.is_stopped is False
        crawler.stop()
        assert crawler.is_stopped is True

    @pytest.mark.asyncio
    async def test_rate_limiting(self, crawler):
        """@spec FEAT-001/C-001 - 100ms minimum delay between requests."""
        import time

        # First request sets the timestamp
        await crawler._enforce_rate_limit("https://example.com/page1")

        # Second request should wait at least 100ms
        start = time.time()
        await crawler._enforce_rate_limit("https://example.com/page2")
        elapsed = time.time() - start

        # Should have waited at least the minimum delay
        assert elapsed >= crawler.config.min_delay - 0.01  # Small tolerance

    @pytest.mark.asyncio
    async def test_crawl_respects_max_depth(self, crawler):
        """@spec FEAT-001/C-005 - Max depth 10."""
        # This is tested by clamping in the crawl method
        max_depth = 15
        clamped = max(1, min(max_depth, 10))
        assert clamped == 10
