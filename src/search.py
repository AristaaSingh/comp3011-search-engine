"""
search.py — Query the inverted index.

Provides the logic behind two CLI commands:

  print <word>
      Shows every page a word appears on, with its frequency and positions.

  find <word> [word2 ...]
      Returns all pages that contain every word in the query (AND logic).
      For a single word this is just all pages it appears on.
      For multiple words only pages containing ALL of them are returned.

Cases explicitly handled:
  1. Word not found   — clear message telling the user which word is missing
  2. Empty query      — usage hint printed instead of a confusing empty result
  3. Mixed case       — all input lowercased before lookup, so Good == good
  4. Multi-word query — set intersection, every word must appear on the page
"""

import logging
from src.indexer import IndexType

logger = logging.getLogger(__name__)


def find_pages(index: IndexType, words: list[str]) -> tuple[list[str], list[str]]:
    """
    Return matching page URLs and any words that were missing from the index.

    Returns a tuple of (results, missing_words) so the caller can give a
    specific message for each outcome:
      - missing_words non-empty  → one or more words not in the index at all
      - results empty            → words exist but no page contains all of them
      - results non-empty        → pages found

    Case-insensitive: all words are lowercased before lookup.
    Multi-word: uses set intersection so every word must be on the page (AND).
    """
    # Case 2: empty query — caller should catch this before calling, but
    # guard here too so the function is safe to call independently
    if not words:
        return [], []

    # Case 3: mixed case — normalise everything to lowercase
    words = [w.lower() for w in words]

    # Case 1: word not in index — collect all missing words before returning
    # so the message can name exactly which word(s) weren't found
    missing = [w for w in words if w not in index]
    if missing:
        return [], missing

    # Case 4: multi-word query — intersect page sets so only pages containing
    # every word are returned
    page_sets = [set(index[w].keys()) for w in words]
    matching = page_sets[0].intersection(*page_sets[1:])
    return sorted(matching), []


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
    # Case 2: empty input
    word = word.strip().lower()
    if not word:
        print("Usage: print <word>")
        return

    # Case 1: word not in index
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

    Gives a specific message for each failure case so the user always
    knows exactly why there are no results.

    Example output for 'find good friends':
        Results for 'good friends' — 2 word(s), 1 page(s) found:

          https://quotes.toscrape.com/page/3/
    """
    # Case 2: empty query
    words = query.strip().split()
    if not words:
        print("Usage: find <word> [word2 ...]")
        return

    results, missing = find_pages(index, words)

    # Case 1: one or more words not in the index at all
    if missing:
        print(f"'{', '.join(missing)}' not found in the index.")
        return

    # Case 4 (no overlap): words exist but no page contains all of them
    if not results:
        print(f"No pages contain all of: {', '.join(words)}")
        return

    # Success — show matching pages
    print(f"\nResults for '{query.strip()}' — {len(words)} word(s), {len(results)} page(s) found:\n")
    for url in results:
        print(f"  {url}")
    print()
