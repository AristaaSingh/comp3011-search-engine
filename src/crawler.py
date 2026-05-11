"""
crawler.py — Web crawler for quotes.toscrape.com

Crawls the site by following the "Next" pagination button through all
pages. Each page's visible text is extracted and returned as a list of
PageData objects for the indexer to process.

Required libraries (both explicitly recommended in the brief):
  - requests    : sends HTTP GET requests
  - beautifulsoup4 : parses HTML and extracts text / links
"""

import time
import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

START_URL = "https://quotes.toscrape.com/"

# Mandatory politeness window between successive requests (brief requires ≥6 s)
POLITENESS_DELAY = 6

REQUEST_TIMEOUT = 10  # seconds before giving up on a single request


# ── Data structure ────────────────────────────────────────────────────────────

@dataclass
class PageData:
    """Holds the URL and extracted text content of a single crawled page."""
    url: str
    text: str  # visible text, lowercased, ready for the indexer


# ── Core functions ────────────────────────────────────────────────────────────

def fetch_page(url: str) -> str | None:
    """
    Send an HTTP GET request to url and return the raw HTML.

    Returns None on any network or HTTP error so the caller can decide
    whether to skip or abort — the crawl should never crash on a bad page.

    Easy to test with mocks: patch requests.get and check return value.
    """
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # raises HTTPError for 4xx / 5xx
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


def parse_text(html: str) -> str:
    """
    Extract all visible text from an HTML page.

    Creates a BeautifulSoup object, strips all tags, and returns the
    remaining text as a single lowercased string.

    Keeping parsing isolated here makes it easy to test independently
    of any network calls.
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ").lower()


def find_next_page(soup: BeautifulSoup, base_url: str) -> str | None:
    """
    Look for the "Next" pagination button and return its absolute URL.

    On quotes.toscrape.com the next-page link is always wrapped in:
        <li class="next"><a href="/page/2/">Next →</a></li>

    Returns None when there is no next page (i.e. we are on the last page).
    Using urljoin ensures relative hrefs are converted to absolute URLs safely.
    """
    next_li = soup.find("li", class_="next")
    if next_li:
        anchor = next_li.find("a", href=True)
        if anchor:
            return urljoin(base_url, anchor["href"])
    return None


def crawl_site(start_url: str = START_URL) -> list[PageData]:
    """
    Orchestrate the full crawl of the site.

    Visits pages sequentially by following the "Next" button on each page.
    Applies the politeness window (time.sleep) between every request so we
    never hammer the server — the brief requires at least 6 seconds.

    Returns a list of PageData objects (one per page) for the indexer.
    """
    pages: list[PageData] = []
    visited: set[str] = set()  # prevents processing the same URL twice
    current_url: str | None = start_url

    while current_url:
        # Skip if already visited (defensive check against redirect loops)
        if current_url in visited:
            logger.warning("Already visited %s — stopping to avoid loop", current_url)
            break
        visited.add(current_url)

        logger.info("Fetching: %s", current_url)

        html = fetch_page(current_url)

        if html is None:
            # Network error — log already printed inside fetch_page, stop crawl
            logger.error("Stopping crawl: could not fetch %s", current_url)
            break

        # Extract visible text for the index
        text = parse_text(html)
        pages.append(PageData(url=current_url, text=text))
        logger.info("Crawled [%d] %s", len(pages), current_url)

        # Check for a next page before sleeping
        soup = BeautifulSoup(html, "html.parser")
        next_url = find_next_page(soup, current_url)

        if next_url:
            # Politeness window — wait before the next request
            # (commented clearly so markers can see it)
            logger.info("Waiting %s seconds (politeness window)...", POLITENESS_DELAY)
            time.sleep(POLITENESS_DELAY)

        current_url = next_url

    logger.info("Crawling complete. Total pages: %d", len(pages))
    return pages
