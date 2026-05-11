"""
search.py — Query the inverted index.

Provides the logic behind two CLI commands:

  print <word>
      Shows every page a word appears on, with its frequency and positions.

  find <word> [word2 ...]
      Returns all pages that contain every word in the query (AND logic).
      For a single word this is just all pages it appears on.
      For multiple words only pages containing ALL of them are returned.

Search is case-insensitive — queries are lowercased before lookup.
"""

import logging
from src.indexer import IndexType

logger = logging.getLogger(__name__)


def find_pages(index: IndexType, words: list[str]) -> list[str]:
    """
    Return a sorted list of URLs that contain every word in the query.

    Uses set intersection: builds a set of pages for each word then keeps
    only the pages that appear in all sets. This gives AND behaviour —
    every word must be present on the page for it to appear in results.

    Returns an empty list if any word is not in the index or if no page
    contains all words.

    Case-insensitive: all words are lowercased before lookup.
    """
    if not words:
        return []

    words = [w.lower() for w in words]

    # Collect the set of pages for each word — bail early if any word
    # is missing from the index entirely
    page_sets: list[set[str]] = []
    for word in words:
        if word not in index:
            logger.info("'%s' not found in index", word)
            return []
        page_sets.append(set(index[word].keys()))

    # Intersect all sets — pages must contain every query word
    matching = page_sets[0].intersection(*page_sets[1:])
    return sorted(matching)


def print_word(index: IndexType, word: str) -> None:
    """
    Print the full index entry for a single word.

    Shows every page the word appears on with its frequency and positions.

    Example output:
        'life' found on 3 page(s):

          https://quotes.toscrape.com/
            frequency : 5
            positions : [2, 14, 31, 44, 60]
    """
    word = word.strip().lower()

    if not word:
        print("Usage: print <word>")
        return

    if word not in index:
        print(f"'{word}' was not found in the index.")
        return

    pages = index[word]
    print(f"\n'{word}' found on {len(pages)} page(s):\n")
    for url, stats in pages.items():
        print(f"  {url}")
        print(f"    frequency : {stats['frequency']}")
        print(f"    positions : {stats['positions']}")
    print()


def find_and_print(index: IndexType, query: str) -> None:
    """
    Parse a query string, find matching pages, and print the results.

    Splits the query into individual words and passes them to find_pages.
    Handles edge cases: empty query, words not in the index, no matches.

    Example output for 'find good friends':
        Results for 'good friends' — 2 word(s), 1 page(s) found:

          https://quotes.toscrape.com/page/3/
    """
    words = query.strip().split()

    if not words:
        print("Usage: find <word> [word2 ...]")
        return

    results = find_pages(index, words)

    if not results:
        print(f"No pages found containing: {', '.join(w.lower() for w in words)}")
        return

    print(f"\nResults for '{query.strip()}' — {len(words)} word(s), {len(results)} page(s) found:\n")
    for url in results:
        print(f"  {url}")
    print()
