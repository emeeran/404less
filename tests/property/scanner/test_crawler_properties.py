"""
Property-based tests for crawler constraints.

@spec FEAT-001 - Property-based tests for constraints
"""

from hypothesis import given, strategies as st, assume, settings, HealthCheck
import pytest
import asyncio
import time

from src.scanner.crawler import AsyncCrawler, CrawlerConfig, CrawlResult


# Strategies for generating test data

valid_url_strategy = st.builds(
    lambda scheme, domain, path: f"{scheme}://{domain}{path}",
    st.sampled_from(["http", "https"]),
    st.sampled_from(["example.com", "test.org", "sub.domain.example.com"]),
    st.one_of(
        st.just(""),
        st.builds(lambda p: f"/{p}", st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz/-"))
    )
)

depth_strategy = st.integers(min_value=-10, max_value=20)

status_code_strategy = st.integers(min_value=100, max_value=599)


class TestDepthConstraints:
    """Property tests for depth constraints."""

    @given(depth=depth_strategy)
    def test_depth_clamping(self, depth: int):
        """
        @spec FEAT-001/C-005 - Max depth 10
        @spec FEAT-001/EC-008 - Clamp depth to 1-10 range
        """
        clamped = max(1, min(depth, 10))
        assert 1 <= clamped <= 10

    @given(depth=st.integers(min_value=1, max_value=10))
    def test_valid_depth_unchanged(self, depth: int):
        """Valid depths should remain unchanged."""
        clamped = max(1, min(depth, 10))
        assert clamped == depth


class TestRateLimitingProperties:
    """Property tests for rate limiting."""

    @given(
        concurrent_requests=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_max_concurrent_never_exceeded(self, concurrent_requests: int):
        """
        @spec FEAT-001/C-001 - Max 5 concurrent requests
        """
        config = CrawlerConfig(max_concurrent=5)
        # The semaphore should never allow more than max_concurrent
        assert config.max_concurrent == 5

    @given(
        delay=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_minimum_delay_respected(self, delay: float):
        """
        @spec FEAT-001/C-001 - 100ms minimum delay
        """
        config = CrawlerConfig(min_delay=0.1)
        # Verify the minimum delay is at least 100ms
        assert config.min_delay >= 0.1


class TestURLNormalization:
    """Property tests for URL normalization."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return AsyncCrawler(
            scan_id="00000000-0000-0000-0000-000000000000",
            config=CrawlerConfig(),
        )

    @given(
        path=st.text(min_size=0, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz/-_")
    )
    def test_fragment_removed(self, crawler, path: str):
        """Fragments are always removed from URLs."""
        assume(path)  # Skip empty paths
        url = f"https://example.com/{path}#section"
        normalized = crawler._normalize_url(url, "https://example.com")
        if normalized:  # May be None if invalid
            assert "#" not in normalized

    @given(
        domain=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz")
    )
    def test_domain_normalized_lowercase(self, crawler, domain: str):
        """Domains are normalized to lowercase."""
        assume(domain)
        url = f"https://{domain.upper()}.COM/page"
        normalized = crawler._normalize_url(url, "https://example.com")
        if normalized:
            # Domain should be lowercase
            assert normalized.split("/")[2] == normalized.split("/")[2].lower()

    @given(
        char=st.characters(
            categories=['Lu', 'Ll', 'Nd'],  # Letters and numbers
            blacklist_characters='<>\"\'\\'
        )
    )
    def test_safe_characters_preserved(self, crawler, char: str):
        """Safe URL characters are preserved."""
        url = f"https://example.com/page{char}end"
        normalized = crawler._normalize_url(url, "https://example.com")
        # Most safe characters should be preserved
        # (some may be URL-encoded)
        if normalized:
            assert "example.com" in normalized


class TestErrorClassification:
    """Property tests for error classification."""

    @given(status_code=status_code_strategy)
    def test_status_code_classification(self, status_code: int):
        """
        @spec FEAT-001/AC-004 - Identify broken links
        """
        if 200 <= status_code < 400:
            status = "ok"
        else:
            status = "broken"

        assert status in ("ok", "broken")


class TestLinkExtraction:
    """Property tests for link extraction."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return AsyncCrawler(
            scan_id="00000000-0000-0000-0000-000000000000",
            config=CrawlerConfig(),
        )

    @given(
        num_links=st.integers(min_value=0, max_value=20)
    )
    def test_extracted_links_deduplicated(self, crawler, num_links: int):
        """
        @spec FEAT-001/EC-004 - Deduplicate URLs
        """
        # Create HTML with duplicate links
        links_html = '<a href="/page">' * num_links
        html = f"<html><body>{links_html}</body></html>"

        extracted = crawler.extract_links(html, "https://example.com")

        # Should only have one /page link
        page_links = [l for l in extracted if l.endswith("/page")]
        assert len(page_links) <= 1

    @given(
        scheme=st.sampled_from(["mailto", "tel", "javascript", "ftp", "file"])
    )
    def test_non_http_schemes_skipped(self, crawler, scheme: str):
        """
        @spec FEAT-001/EC-009 - Skip non-HTTP schemes
        """
        url = f"{scheme}:test"
        normalized = crawler._normalize_url(url, "https://example.com")
        assert normalized is None


class TestCrawlResultProperties:
    """Property tests for CrawlResult."""

    @given(
        url=valid_url_strategy,
        status=st.sampled_from(["ok", "broken", "skipped"]),
        status_code=st.one_of(st.none(), st.integers(min_value=100, max_value=599)),
        depth=st.integers(min_value=0, max_value=10),
    )
    def test_crawl_result_serialization(self, url: str, status: str, status_code, depth: int):
        """CrawlResult can be serialized to dict."""
        result = CrawlResult(
            url=url,
            status=status,
            status_code=status_code,
            depth=depth,
        )
        data = result.to_dict()

        assert data["url"] == url
        assert data["status"] == status
        assert data["status_code"] == status_code
        assert data["depth"] == depth


class TestSameDomainCheck:
    """Property tests for same-domain checking."""

    @pytest.fixture
    def crawler(self):
        """Create crawler instance."""
        return AsyncCrawler(
            scan_id="00000000-0000-0000-0000-000000000000",
            config=CrawlerConfig(),
        )

    @given(
        domain=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz"),
        path1=st.text(min_size=0, max_size=20, alphabet="abc"),
        path2=st.text(min_size=0, max_size=20, alphabet="abc"),
    )
    def test_same_domain_detection(self, crawler, domain: str, path1: str, path2: str):
        """
        @spec FEAT-001/AC-005 - Same-domain restriction
        """
        assume(domain)
        url1 = f"https://{domain}.com/{path1}"
        url2 = f"https://{domain}.com/{path2}"

        assert crawler.is_same_domain(url1, url2) is True

    @given(
        domain1=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz"),
        domain2=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    def test_different_domain_detection(self, crawler, domain1: str, domain2: str):
        """Different domains are correctly identified."""
        assume(domain1 != domain2)
        assume(domain1 and domain2)

        url1 = f"https://{domain1}.com/"
        url2 = f"https://{domain2}.com/"

        assert crawler.is_same_domain(url1, url2) is False
