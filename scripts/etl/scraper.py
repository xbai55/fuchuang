"""
HTTP scraper for fetching fraud case web pages.
Handles encoding detection, retries, and polite crawl delays.
"""

import random
import time
from typing import Optional

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def fetch_url(url: str, timeout: int = 15, retries: int = 2) -> Optional[str]:
    """Fetch a URL; returns HTML string or None on failure."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException as e:
            if attempt < retries:
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f"[scraper] Attempt {attempt + 1} failed for {url}: {e}. Retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                print(f"[scraper] Failed to fetch {url}: {e}")
                return None


def fetch_urls(urls: list[str], delay: float = 1.5) -> dict[str, Optional[str]]:
    """Fetch multiple URLs with a polite delay between requests."""
    results: dict[str, Optional[str]] = {}
    for i, url in enumerate(urls):
        if i > 0:
            jitter = random.uniform(0, 0.5)
            time.sleep(delay + jitter)
        print(f"[scraper] ({i + 1}/{len(urls)}) {url}")
        results[url] = fetch_url(url)
    return results


def load_url_list(file_path: str) -> list[str]:
    """Read a plain-text file of URLs (one per line), ignoring blank lines and # comments."""
    urls = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls
