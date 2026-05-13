"""
crawler.py: Web crawler for quotes.toscrape.com

Crawls the entire site using a BFS queue, following every internal link
found on each page (quote pages, author pages, tag pages, etc.).
Each page's visible text is extracted and returned as a list of
PageData objects for the indexer to process.

Required libraries (both explicitly recommended in the brief):
  - requests : sends HTTP GET requests
  - beautifulsoup4 : parses HTML and extracts text / links
"""

import time
import logging
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Constants

START_URL = "https://quotes.toscrape.com/"

# Mandatory politeness window between successive requests (at least 6s)
POLITENESS_DELAY = 6

# seconds before giving up on a single request
REQUEST_TIMEOUT = 10


# Data structure
@dataclass
class PageData:
    """Holds the URL and extracted text content of a single crawled page."""
    url: str
    text: str # visible text, lowercased, ready for the indexer


def fetch_page(url: str) -> str | None:
    """
    Send an HTTP GET request to url and return the raw HTML.

    Returns None on any network or HTTP error so the caller can decide
    whether to skip, the crawl should never crash on a bad page.
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


def find_all_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Extract every internal link from a page and return them as absolute URLs.

    Finds all <a href="..."> anchors, converts relative paths to absolute
    URLs using urljoin, then keeps only links that belong to the same domain
    as base_url. Fragment-only links (eg #section) are discarded.

    This is what allows the crawler to discover author pages, tag pages,
    and all other sections of the site, not just the paginated quote pages.
    """
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        # Build an absolute URL and strip any fragment (#section)
        absolute = urljoin(base_url, anchor["href"]).split("#")[0]

        if not absolute or absolute in seen:
            continue

        parsed = urlparse(absolute)
        # Only keep links that are on the same domain and use http/https
        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            links.append(absolute)
            seen.add(absolute)

    return links


def crawl_site(start_url: str = START_URL) -> list[PageData]:
    """
    Perform the full crawl of the site using a BFS queue.

    Starts at start_url and follows every internal link discovered on each
    page, so it visits quote pages, author pages, tag pages, and anything
    else linked from within the site.

    Applies the politeness window (time.sleep) between every request so we
    never hammer the server.

    Returns a list of PageData objects (one per page) for the indexer.
    """
    pages: list[PageData] = []
    visited: set[str] = set() # prevents fetching the same URL twice
    queue: deque[str] = deque([start_url]) # BFS queue, deque gives O(1) popleft vs O(n) for list.pop(0)

    first_request = True # no sleep before the very first request

    while queue:
        current_url = queue.popleft() # O(1) removal from front

        # Skip URLs already processed (queue may contain duplicates)
        if current_url in visited:
            continue
        visited.add(current_url)

        # Politeness window, wait before every request except the first
        if not first_request:
            logger.info("Waiting %s seconds (politeness window)...", POLITENESS_DELAY)
            time.sleep(POLITENESS_DELAY)
        first_request = False

        logger.info("Fetching: %s", current_url)
        html = fetch_page(current_url)

        if html is None:
            # Network / HTTP error log already printed inside fetch_page
            logger.warning("Skipping %s: could not fetch", current_url)
            continue # skip this page, keep crawling the rest of the queue

        # Extract visible text for the index
        text = parse_text(html)
        pages.append(PageData(url=current_url, text=text))
        print(f"  [{len(pages)}] {current_url}")
        logger.info("Crawled [%d] %s", len(pages), current_url)

        # Discover new links and add unseen ones to the queue
        soup = BeautifulSoup(html, "html.parser")
        for link in find_all_links(soup, current_url):
            if link not in visited:
                queue.append(link) # append to back, popleft from front = FIFO

    logger.info("Crawling complete. Total pages: %d", len(pages))
    return pages
