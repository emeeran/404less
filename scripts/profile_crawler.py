"""
Performance Profiling Script for Crawler

Identifies bottlenecks in the crawler pipeline:
1. Link extraction (HTML parsing)
2. URL normalization
3. Robots.txt checking
4. HTTP requests

Usage:
    uv run python scripts/profile_crawler.py
"""

import asyncio
import cProfile
import io
import pstats
import time
import tracemalloc
from statistics import mean, stdev
from uuid import uuid4

# Add src to path
import sys
sys.path.insert(0, ".")

from src.scanner.crawler import AsyncCrawler, CrawlerConfig, LinkExtractor
from src.scanner.robots import RobotsChecker


# Sample HTML for testing (simulating a real page with many links)
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="/css/style.css">
    <link rel="icon" href="/favicon.ico">
    <script src="/js/main.js"></script>
    <script src="/js/analytics.js"></script>
</head>
<body>
    <nav>
        <a href="/">Home</a>
        <a href="/about">About</a>
        <a href="/contact">Contact</a>
        <a href="/products">Products</a>
        <a href="/services">Services</a>
        <a href="/blog">Blog</a>
        <a href="/faq">FAQ</a>
        <a href="/terms">Terms</a>
        <a href="/privacy">Privacy</a>
    </nav>
    <main>
        <h1>Welcome</h1>
        <img src="/images/hero.jpg" alt="Hero">
        <img src="/images/banner.png" alt="Banner">
        <section>
            <a href="/products/item1">Product 1</a>
            <a href="/products/item2">Product 2</a>
            <a href="/products/item3">Product 3</a>
            <a href="/products/item4">Product 4</a>
            <a href="/products/item5">Product 5</a>
        </section>
        <section>
            <iframe src="/embeds/video1"></iframe>
            <iframe src="/embeds/map"></iframe>
            <source src="/media/audio.mp3">
            <track src="/subs/en.vtt">
        </section>
        <footer>
            <a href="mailto:contact@example.com">Email</a>
            <a href="tel:+1234567890">Phone</a>
            <a href="javascript:void(0)">Click</a>
            <a href="#section1">Jump</a>
            <embed src="/flash/old.swf">
            <area href="/map/region1" alt="Region">
        </footer>
    </main>
</body>
</html>
"""

# Large HTML with many links for stress testing
LARGE_HTML = SAMPLE_HTML * 100  # Simulate 100x the content


def profile_link_extraction():
    """Profile the LinkExtractor with different HTML sizes."""
    print("\n" + "=" * 60)
    print("PROFILE: Link Extraction")
    print("=" * 60)

    extractor = LinkExtractor()

    # Profile small HTML
    print("\n--- Small HTML (1x) ---")
    profiler = cProfile.Profile()
    profiler.enable()

    for _ in range(1000):
        extractor.feed(SAMPLE_HTML)
        extractor.links.clear()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

    # Profile large HTML
    print("\n--- Large HTML (100x) ---")
    extractor_large = LinkExtractor()
    profiler2 = cProfile.Profile()
    profiler2.enable()

    for _ in range(100):
        extractor_large.feed(LARGE_HTML)
        extractor_large.links.clear()

    profiler2.disable()
    stats2 = pstats.Stats(profiler2)
    stats2.sort_stats('cumulative')
    stats2.print_stats(10)


def time_link_extraction():
    """Time link extraction with detailed measurements."""
    print("\n" + "=" * 60)
    print("TIMING: Link Extraction")
    print("=" * 60)

    extractor = LinkExtractor()

    # Warmup
    for _ in range(100):
        extractor.feed(SAMPLE_HTML)
        extractor.links.clear()

    # Time small HTML
    times = []
    for _ in range(1000):
        start = time.perf_counter()
        extractor.feed(SAMPLE_HTML)
        links = extractor.links.copy()
        extractor.links.clear()
        times.append(time.perf_counter() - start)

    print(f"\nSmall HTML ({len(SAMPLE_HTML)} bytes):")
    print(f"  Mean:   {mean(times)*1000:.4f} ms")
    print(f"  Std:    {stdev(times)*1000:.4f} ms")
    print(f"  Min:    {min(times)*1000:.4f} ms")
    print(f"  Max:    {max(times)*1000:.4f} ms")
    print(f"  Links:  {len(links)}")

    # Time large HTML
    times_large = []
    for _ in range(100):
        start = time.perf_counter()
        extractor.feed(LARGE_HTML)
        links = extractor.links.copy()
        extractor.links.clear()
        times_large.append(time.perf_counter() - start)

    print(f"\nLarge HTML ({len(LARGE_HTML)} bytes):")
    print(f"  Mean:   {mean(times_large)*1000:.4f} ms")
    print(f"  Std:    {stdev(times_large)*1000:.4f} ms")
    print(f"  Min:    {min(times_large)*1000:.4f} ms")
    print(f"  Max:    {max(times_large)*1000:.4f} ms")


def profile_url_normalization():
    """Profile URL normalization with various URL types."""
    print("\n" + "=" * 60)
    print("PROFILE: URL Normalization")
    print("=" * 60)

    crawler = AsyncCrawler(scan_id=uuid4(), config=CrawlerConfig())

    test_urls = [
        "https://example.com/page",
        "/relative/path",
        "mailto:test@example.com",
        "javascript:void(0)",
        "https://example.com/page#section",
        "https://EXAMPLE.COM/Page?query=1",
        "/path/with/<script>alert(1)</script>",
        "https://example.com/path?param=value&other=123",
    ] * 100  # Repeat for profiling

    profiler = cProfile.Profile()
    profiler.enable()

    for url in test_urls:
        crawler._normalize_url(url, "https://example.com")

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

    # Time measurements
    print("\n--- Timing ---")
    times = []
    for _ in range(1000):
        start = time.perf_counter()
        for url in test_urls[:8]:
            crawler._normalize_url(url, "https://example.com")
        times.append(time.perf_counter() - start)

    print(f"Normalize 8 URLs:")
    print(f"  Mean: {mean(times)*1000:.4f} ms")
    print(f"  Per URL: {mean(times)*1000/8:.4f} ms")


def profile_extract_links():
    """Profile the full extract_links method."""
    print("\n" + "=" * 60)
    print("PROFILE: extract_links (Full Pipeline)")
    print("=" * 60)

    crawler = AsyncCrawler(scan_id=uuid4(), config=CrawlerConfig())

    profiler = cProfile.Profile()
    profiler.enable()

    for _ in range(500):
        crawler.extract_links(SAMPLE_HTML, "https://example.com")

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(15)

    # Time measurements
    print("\n--- Timing ---")
    times = []
    for _ in range(1000):
        start = time.perf_counter()
        links = crawler.extract_links(SAMPLE_HTML, "https://example.com")
        times.append(time.perf_counter() - start)

    print(f"Extract links from small HTML:")
    print(f"  Mean:  {mean(times)*1000:.4f} ms")
    print(f"  Links: {len(links)}")


def memory_profile_extraction():
    """Profile memory usage during extraction."""
    print("\n" + "=" * 60)
    print("MEMORY: Link Extraction")
    print("=" * 60)

    tracemalloc.start()

    # Snapshot before
    snapshot1 = tracemalloc.take_snapshot()

    # Do work
    extractor = LinkExtractor()
    for _ in range(1000):
        extractor.feed(LARGE_HTML)
        extractor.links.clear()

    # Snapshot after
    snapshot2 = tracemalloc.take_snapshot()

    tracemalloc.stop()

    # Compare
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    print("\nTop 10 memory allocations:")
    for stat in top_stats[:10]:
        print(stat)


async def profile_robots_checker():
    """Profile robots.txt checking (simulated)."""
    print("\n" + "=" * 60)
    print("PROFILE: Robots.txt Checker")
    print("=" * 60)

    checker = RobotsChecker(timeout=1)

    # Pre-populate cache to simulate warmed cache
    checker._robots_cache["https://example.com"] = """
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/
"""

    profiler = cProfile.Profile()
    profiler.enable()

    # Test with cached robots.txt (simulating repeated checks)
    for _ in range(1000):
        checker._parse_robots(
            checker._robots_cache["https://example.com"],
            "/page/test",
            "*"
        )

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

    # Time the parsing
    print("\n--- Timing (cached robots.txt) ---")
    times = []
    for _ in range(1000):
        start = time.perf_counter()
        checker._parse_robots(
            checker._robots_cache["https://example.com"],
            "/admin/secret",
            "*"
        )
        times.append(time.perf_counter() - start)

    print(f"Parse robots.txt:")
    print(f"  Mean: {mean(times)*1000000:.2f} µs")


async def profile_rate_limiting():
    """Profile rate limiting overhead."""
    print("\n" + "=" * 60)
    print("PROFILE: Rate Limiting")
    print("=" * 60)

    crawler = AsyncCrawler(scan_id=uuid4(), config=CrawlerConfig(min_delay=0.0))

    profiler = cProfile.Profile()
    profiler.enable()

    for _ in range(1000):
        await crawler._enforce_rate_limit("https://example.com/page1")
        await crawler._enforce_rate_limit("https://other.com/page1")

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)


def run_all_profiles():
    """Run all profiling tests."""
    print("\n" + "=" * 60)
    print("CRAWLER PERFORMANCE PROFILING")
    print("=" * 60)

    # Synchronous profiles
    profile_link_extraction()
    time_link_extraction()
    profile_url_normalization()
    profile_extract_links()
    memory_profile_extraction()

    # Async profiles
    asyncio.run(profile_robots_checker())
    asyncio.run(profile_rate_limiting())

    print("\n" + "=" * 60)
    print("PROFILING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_all_profiles()
