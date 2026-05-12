"""
test_crawler.py: Tests for crawler.py

Covers all four functions:
  1. fetch_page: real network tests against quotes.toscrape.com
  2. parse_text: HTML tag stripping and lowercasing
  3. find_all_links: internal link discovery and filtering
  4. crawl_site: full crawl orchestration using mocked fetch_page
"""

import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup

from src.crawler import fetch_page, parse_text, find_all_links, crawl_site

BASE_URL = "https://quotes.toscrape.com/"
INVALID_URL = "https://quotes.toscrape.com/this-page-does-not-exist-404"


# fetch_page: real network tests

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


# parse_text: HTML parsing tests

def test_parse_text_extracts_text():
    """Basic paragraph text should be extracted from HTML."""
    html = "<html><body><p>Hello world</p></body></html>"
    assert "hello world" in parse_text(html)


def test_parse_text_strips_tags():
    """HTML tags should not appear in the output."""
    html = "<html><body><p>Hello</p></body></html>"
    result = parse_text(html)
    assert "<p>" not in result
    assert "<html>" not in result


def test_parse_text_returns_lowercase():
    """All output should be lowercased regardless of input case."""
    html = "<html><body><p>HELLO WORLD</p></body></html>"
    result = parse_text(html)
    assert "hello world" in result
    assert "HELLO" not in result


def test_parse_text_empty_html():
    """Empty input should return a string without crashing."""
    result = parse_text("")
    assert isinstance(result, str)


def test_parse_text_multiple_elements():
    """Text from multiple elements should all be present in output."""
    html = "<html><body><h1>Title</h1><p>Body text</p></body></html>"
    result = parse_text(html)
    assert "title" in result
    assert "body text" in result


# find_all_links: link extraction tests

def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_find_all_links_converts_relative_to_absolute():
    """Relative hrefs should be returned as absolute URLs."""
    soup = make_soup('<a href="/page/2/">Next</a>')
    links = find_all_links(soup, BASE_URL)
    assert "https://quotes.toscrape.com/page/2/" in links


def test_find_all_links_excludes_external_domains():
    """Links pointing to a different domain should be excluded."""
    soup = make_soup('<a href="https://google.com/">External</a>')
    links = find_all_links(soup, BASE_URL)
    assert not any("google.com" in link for link in links)


def test_find_all_links_strips_fragments():
    """Fragment anchors should not appear in returned links."""
    soup = make_soup('<a href="/page/2/#section">Jump</a>')
    links = find_all_links(soup, BASE_URL)
    assert all("#" not in link for link in links)


def test_find_all_links_no_duplicates():
    """The same URL appearing in multiple anchors should only appear once."""
    soup = make_soup(
        '<a href="/page/2/">Next</a><a href="/page/2/">Also next</a>'
    )
    links = find_all_links(soup, BASE_URL)
    assert links.count("https://quotes.toscrape.com/page/2/") == 1


def test_find_all_links_empty_page():
    """A page with no anchor tags should return an empty list."""
    soup = make_soup("<html><body><p>No links here</p></body></html>")
    links = find_all_links(soup, BASE_URL)
    assert links == []


def test_find_all_links_includes_absolute_internal():
    """Absolute hrefs on the same domain should be included."""
    soup = make_soup(
        '<a href="https://quotes.toscrape.com/author/einstein/">Author</a>'
    )
    links = find_all_links(soup, BASE_URL)
    assert "https://quotes.toscrape.com/author/einstein/" in links


# crawl_site: orchestration tests using mocked fetch_page
# time.sleep is also mocked so tests run instantly without the politeness delay

HOME_HTML = """
<html><body>
  <p>Quote on home page</p>
  <a href="/page/2/">Next</a>
</body></html>
"""

PAGE_2_HTML = """
<html><body>
  <p>Quote on page two</p>
</body></html>
"""


def fake_fetch_two_pages(url):
    if url == BASE_URL:
        return HOME_HTML
    if url == "https://quotes.toscrape.com/page/2/":
        return PAGE_2_HTML
    return None


def test_crawl_site_returns_correct_number_of_pages():
    """crawl_site should return one PageData per crawled page."""
    with patch("src.crawler.fetch_page", side_effect=fake_fetch_two_pages):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)
    assert len(pages) == 2


def test_crawl_site_records_correct_urls():
    """Each PageData should store the URL of the page it came from."""
    with patch("src.crawler.fetch_page", side_effect=fake_fetch_two_pages):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)
    urls = [p.url for p in pages]
    assert BASE_URL in urls
    assert "https://quotes.toscrape.com/page/2/" in urls


def test_crawl_site_skips_failed_pages():
    """If fetch_page returns None for a URL, it should be skipped without crashing."""
    def fake_fetch(url):
        if url == BASE_URL:
            return HOME_HTML
        return None

    with patch("src.crawler.fetch_page", side_effect=fake_fetch):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)

    assert len(pages) == 1
    assert pages[0].url == BASE_URL


def test_crawl_site_does_not_revisit_urls():
    """A page that links back to itself should only be crawled once."""
    self_link_html = """
    <html><body>
      <p>Page with self link</p>
      <a href="/">Home again</a>
    </body></html>
    """
    with patch("src.crawler.fetch_page", return_value=self_link_html):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)
    assert len(pages) == 1


def test_crawl_site_text_is_extracted():
    """PageData text should contain the visible text from the crawled page."""
    with patch("src.crawler.fetch_page", return_value=HOME_HTML):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)
    assert "quote on home page" in pages[0].text


# parse_text: script and style tag exclusion

def test_parse_text_excludes_script_tag_content():
    """JavaScript inside script tags should not appear in the extracted text."""
    html = "<html><body><p>Hello</p><script>function secret() {}</script></body></html>"
    result = parse_text(html)
    assert "secret" not in result
    assert "function" not in result


def test_parse_text_excludes_style_tag_content():
    """CSS inside style tags should not appear in the extracted text."""
    html = "<html><body><p>Hello</p><style>.colorscheme { display: none; }</style></body></html>"
    result = parse_text(html)
    assert "colorscheme" not in result
    assert "display" not in result


# find_all_links: non-http link exclusion

def test_find_all_links_excludes_mailto():
    """mailto: links should not be included in results."""
    soup = make_soup('<a href="mailto:test@example.com">Email us</a>')
    links = find_all_links(soup, BASE_URL)
    assert not any("mailto" in link for link in links)


def test_find_all_links_excludes_javascript():
    """javascript: links should not be included in results."""
    soup = make_soup('<a href="javascript:void(0)">Click</a>')
    links = find_all_links(soup, BASE_URL)
    assert not any("javascript" in link for link in links)


# crawl_site: multi-page chain

def test_crawl_site_follows_chain_of_pages():
    """crawl_site should follow links across a chain of pages, not just one hop."""
    page3_url = "https://quotes.toscrape.com/page/3/"
    page2_html = f'<html><body><p>Page two</p><a href="/page/3/">Next</a></body></html>'
    page3_html = '<html><body><p>Page three</p></body></html>'

    def fake_fetch(url):
        if url == BASE_URL:
            return HOME_HTML
        if url == "https://quotes.toscrape.com/page/2/":
            return page2_html
        if url == page3_url:
            return page3_html
        return None

    with patch("src.crawler.fetch_page", side_effect=fake_fetch):
        with patch("src.crawler.time.sleep"):
            pages = crawl_site(BASE_URL)

    urls = [p.url for p in pages]
    assert page3_url in urls
    assert len(pages) == 3
