"""
crawler.py — Web crawler for quotes.toscrape.com

Performs a breadth-first crawl of the target site, respecting a
politeness window of at least 6 seconds between successive requests.

Returns a list of PageData named tuples, each containing the page URL
and its extracted text content, for the indexer to process.
"""

import time
import logging
from collections import deque
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://quotes.toscrape.com/"
POLITENESS_DELAY = 6  # seconds between requests (required by brief)
REQUEST_TIMEOUT = 10  # seconds before giving up on a single request

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ── Data structure ───────────────────────────────────────────────────────────

@dataclass
class PageData:
    """Holds the URL and extracted text of a single crawled page."""
    url: str
    text: str  # raw lowercased text content of the page


# ── Crawler class ────────────────────────────────────────────────────────────

class Crawler:
    """
    Breadth-first crawler scoped to a single domain.

    Usage:
        crawler = Crawler()
        pages = crawler.crawl()   # returns list[PageData]
    """

    def __init__(
        self,
        start_url: str = BASE_URL,
        politeness_delay: float = POLITENESS_DELAY,
    ):
        self.start_url = start_url
        self.politeness_delay = politeness_delay

        # Extract the allowed domain so we never leave the target site
        parsed = urlparse(start_url)
        self.domain = parsed.scheme + "://" + parsed.netloc

        # HTTP session reuses the same TCP connection across requests
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "COMP3011-SearchEngine/1.0"})

    # ── Public API ───────────────────────────────────────────────────────────

    def crawl(self) -> list[PageData]:
        """
        Crawl the site starting from self.start_url.

        Returns a list of PageData objects (one per successfully fetched page),
        in the order they were visited.
        """
        visited: set[str] = set()
        queue: deque[str] = deque([self.start_url])
        pages: list[PageData] = []

        while queue:
            url = queue.popleft()

            # Normalise and skip if already seen
            url = self._normalise(url)
            if url in visited:
                continue
            visited.add(url)

            # Fetch the page
            html = self._fetch(url)
            if html is None:
                continue  # network error — already logged inside _fetch

            # Parse content and collect outgoing links
            text, links = self._parse(html, url)
            pages.append(PageData(url=url, text=text))
            logger.info("Crawled [%d] %s", len(pages), url)

            # Enqueue new in-domain links
            for link in links:
                if link not in visited:
                    queue.append(link)

            # Politeness window — wait before the next request
            if queue:
                time.sleep(self.politeness_delay)

        return pages

    # ── Private helpers ──────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str | None:
        """
        Fetch a URL and return its HTML as a string, or None on failure.

        All network errors are caught and logged so the crawl can continue.
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP error fetching %s: %s", url, e)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error fetching %s: %s", url, e)
        except requests.exceptions.Timeout:
            logger.warning("Timeout fetching %s", url)
        except requests.exceptions.RequestException as e:
            logger.warning("Request failed for %s: %s", url, e)
        return None

    def _parse(self, html: str, base_url: str) -> tuple[str, list[str]]:
        """
        Parse an HTML page and return:
          - page_text: lowercased visible text (for indexing)
          - links: list of absolute in-domain URLs found on the page
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract visible text and normalise to lowercase
        page_text = soup.get_text(separator=" ").lower()

        # Collect all <a href="..."> links that stay within our domain
        links: list[str] = []
        for tag in soup.find_all("a", href=True):
            absolute = urljoin(base_url, tag["href"])
            if self._is_internal(absolute):
                links.append(self._normalise(absolute))

        return page_text, links

    def _is_internal(self, url: str) -> bool:
        """Return True if url belongs to the same domain as the start URL."""
        return url.startswith(self.domain)

    @staticmethod
    def _normalise(url: str) -> str:
        """
        Strip URL fragments (#section) to avoid crawling the same page twice
        under different fragment identifiers.
        """
        parsed = urlparse(url)
        return parsed._replace(fragment="").geturl()
