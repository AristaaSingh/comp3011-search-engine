"""
test_indexer.py — Tests for indexer.py

Covers:
  1. Basic indexing        — words appear in the index
  2. Frequency correctness — repeated words counted accurately
  3. Position correctness  — positions recorded in order
  4. Multiple pages        — same word tracked across different pages
  5. Edge cases            — empty text, punctuation, very little content
  6. Save / load           — index survives a round-trip to disk as JSON
"""

import json
import pytest
from pathlib import Path

from src.crawler import PageData
from src.indexer import tokenise, add_page_to_index, build_index, save_index, load_index

URL_1 = "https://quotes.toscrape.com/"
URL_2 = "https://quotes.toscrape.com/page/2/"


# ── Helper ────────────────────────────────────────────────────────────────────

def make_page(text: str, url: str = URL_1) -> PageData:
    """Convenience: build a PageData with the given text."""
    return PageData(url=url, text=text)


# ── Test 1: Basic indexing ────────────────────────────────────────────────────

def test_basic_indexing_words_in_index():
    """Both words from a simple two-word page should appear in the index."""
    index = build_index([make_page("hello world")])
    assert "hello" in index
    assert "world" in index


def test_basic_indexing_url_recorded():
    """The page URL should be recorded under each word."""
    index = build_index([make_page("hello world")])
    assert URL_1 in index["hello"]
    assert URL_1 in index["world"]


# ── Test 2: Frequency correctness ─────────────────────────────────────────────

def test_frequency_single_occurrence():
    index = build_index([make_page("hello world")])
    assert index["hello"][URL_1]["frequency"] == 1


def test_frequency_repeated_word():
    """A word appearing twice should have frequency 2."""
    index = build_index([make_page("hello hello")])
    assert index["hello"][URL_1]["frequency"] == 2


def test_frequency_many_repeats():
    index = build_index([make_page("test test test")])
    assert index["test"][URL_1]["frequency"] == 3


# ── Test 3: Position correctness ──────────────────────────────────────────────

def test_positions_single_word():
    index = build_index([make_page("hello")])
    assert index["hello"][URL_1]["positions"] == [0]


def test_positions_repeated_word():
    """'a' appears at positions 0 and 2 in 'a b a'."""
    index = build_index([make_page("a b a")])
    assert index["a"][URL_1]["positions"] == [0, 2]


def test_positions_are_zero_based():
    """First word should be at position 0, second at 1."""
    index = build_index([make_page("first second")])
    assert index["first"][URL_1]["positions"] == [0]
    assert index["second"][URL_1]["positions"] == [1]


# ── Test 4: Multiple pages ────────────────────────────────────────────────────

def test_same_word_across_two_pages():
    """The same word on two pages should have two URL entries."""
    pages = [
        make_page("life is good", url=URL_1),
        make_page("life goes on", url=URL_2),
    ]
    index = build_index(pages)
    assert URL_1 in index["life"]
    assert URL_2 in index["life"]


def test_word_unique_to_one_page():
    """A word only on page 1 should not appear under page 2's URL."""
    pages = [
        make_page("unique word", url=URL_1),
        make_page("different text", url=URL_2),
    ]
    index = build_index(pages)
    assert URL_2 not in index["unique"]


def test_frequencies_tracked_per_page():
    """Frequency counts should be independent per page."""
    pages = [
        make_page("test test", url=URL_1),       # frequency 2 on page 1
        make_page("test", url=URL_2),             # frequency 1 on page 2
    ]
    index = build_index(pages)
    assert index["test"][URL_1]["frequency"] == 2
    assert index["test"][URL_2]["frequency"] == 1


# ── Test 5: Edge cases ────────────────────────────────────────────────────────

def test_empty_text_does_not_crash():
    """An empty page should produce no index entries and not raise."""
    index = build_index([make_page("")])
    assert index == {}


def test_punctuation_is_stripped():
    """'hello!!!' should be indexed as 'hello', not 'hello!!!'."""
    index = build_index([make_page("hello!!!")])
    assert "hello" in index
    assert "hello!!!" not in index


def test_punctuation_only_text():
    """A page containing only punctuation should produce no index entries."""
    index = build_index([make_page("!!! ??? ...")])
    assert index == {}


def test_very_little_content():
    """A page with a single word should index correctly without errors."""
    index = build_index([make_page("alone")])
    assert "alone" in index
    assert index["alone"][URL_1]["frequency"] == 1


def test_mixed_punctuation_and_words():
    """Punctuation attached to words should be stripped cleanly."""
    index = build_index([make_page("it's a great, wonderful life.")])
    assert "it's" in index
    assert "great" in index
    assert "wonderful" in index
    assert "life" in index


# ── Test 6: Save / load round-trip ───────────────────────────────────────────

def test_save_and_load_round_trip(tmp_path):
    """Index saved to disk should load back identical to the original."""
    index = build_index([make_page("hello world")])
    path = tmp_path / "index.json"

    save_index(index, path)
    loaded = load_index(path)

    assert loaded == index


def test_saved_file_is_valid_json(tmp_path):
    """The saved file should be parseable JSON."""
    index = build_index([make_page("hello world")])
    path = tmp_path / "index.json"

    save_index(index, path)

    with open(path) as f:
        parsed = json.load(f)
    assert isinstance(parsed, dict)


def test_load_raises_if_file_missing(tmp_path):
    """load_index should raise FileNotFoundError if no index file exists."""
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path / "nonexistent.json")
