"""
test_crawler.py — Tests for crawler.py

Tests fetch_page against the real quotes.toscrape.com to verify:
  1. At least one URL can be fetched successfully
  2. A valid URL returns non-empty content
  3. An invalid URL is handled gracefully (returns None, no crash)
"""
import pytest
from src.crawler import fetch_page

BASE_URL = "https://quotes.toscrape.com/"
INVALID_URL = "https://quotes.toscrape.com/this-page-does-not-exist-404"


def test_fetches_at_least_one_url():
    """fetch_page should successfully retrieve the homepage."""
    result = fetch_page(BASE_URL)
    assert result is not None


def test_valid_url_returns_non_empty_content():
    """A valid URL should return a non-empty HTML string."""
    result = fetch_page(BASE_URL)
    assert isinstance(result, str)
    assert len(result) > 0


def test_invalid_url_handled_gracefully():
    """A 404 URL should return None without raising an exception."""
    result = fetch_page(INVALID_URL)
    assert result is None
