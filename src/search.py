"""
search.py:  Query the inverted index.

Provides the logic behind two CLI commands:

  print <word>
      Shows every page a word appears on, with its frequency and positions.

  find <word> [word2 ...]
      Returns all pages that contain every word in the query (AND logic).
      For a single word this is just all pages it appears on.
      For multiple words only pages containing ALL of them are returned.

Cases explicitly handled:
  1. Word not found: clear message + "Did you mean?" suggestions via difflib
  2. Empty query: usage hint printed instead of a confusing empty result
  3. Mixed case: all input lowercased before lookup, so Good == good
  4. Multi-word query: set intersection, every word must appear on the page
"""

import math
import difflib
import logging
from src.indexer import IndexType

logger = logging.getLogger(__name__)


def suggest_words(index: IndexType, word: str) -> list[str]:
    """
    Return up to 3 words from the index that closely match word.

    Uses difflib.get_close_matches which computes a similarity ratio based
    on the longest common subsequence. A cutoff of 0.6 means the candidate
    must share at least 60% similarity with the query word. This catches
    common typos (e.g. 'frends' -> 'friends') without suggesting completely
    unrelated words. The cutoff is a deliberate trade-off: lower values
    produce more suggestions but risk irrelevant ones.

    The '__meta__' key is excluded since it is internal metadata, not a word.
    """
    candidates = [k for k in index if k != "__meta__"]
    return difflib.get_close_matches(word, candidates, n=3, cutoff=0.6)


def rank_results(index: IndexType, urls: list[str], words: list[str]) -> list[str]:
    """
    Sort a list of page URLs by normalised TF-IDF relevance to the query.

    For each query word on each page, the score is:
      TF  = frequency / total tokens on that page (normalised term frequency)
      IDF = log(total pages in index / pages containing the word)
      contribution = TF * IDF

    TF normalisation prevents longer pages from being unfairly favoured:
    a word appearing 10 times on an 800-token page scores lower than the
    same word appearing 5 times on a 40-token page, because 10/800 < 5/40.

    IDF ensures rare words carry more weight than common ones. A word that
    appears on every page gets IDF = 0 and contributes nothing to ranking.

    Document lengths (total tokens per page) and total page count are
    precomputed by build_index and stored in the index under "__meta__",
    so they are read once rather than recalculated on every query.

    Example: query "indifference" across 214 pages, appears on 3:
      IDF = log(214 / 3) = 4.27
      page/1: frequency 2, doc length 80  -> TF = 0.025, score = 0.025 * 4.27 = 0.107
      page/2: frequency 1, doc length 20  -> TF = 0.05,  score = 0.05  * 4.27 = 0.214
      page/2 ranks first despite lower raw frequency, because it is shorter.
    """
    if not urls:
        return []

    # Read metadata precomputed by build_index. Fall back to computing on
    # the fly if the index was built without it (e.g., an old index file).
    meta = index.get("__meta__", {})
    if meta:
        total_pages: int = meta["total_pages"]
        doc_lengths: dict[str, int] = meta["doc_lengths"]
    else:
        all_pages: set[str] = {
            url
            for word, page_dict in index.items()
            if word != "__meta__"
            for url in page_dict
        }
        total_pages = len(all_pages)
        doc_lengths = {}
        for word, page_dict in index.items():
            if word != "__meta__":
                for url, stats in page_dict.items():
                    doc_lengths[url] = doc_lengths.get(url, 0) + stats["frequency"]

    def score(url: str) -> float:
        total = 0.0
        doc_len = doc_lengths.get(url, 1) # default to 1 to avoid division by zero
        for word in words:
            if word in index and url in index[word]:
                tf = index[word][url]["frequency"] / doc_len  # normalised TF
                pages_with_word = len(index[word])
                idf = math.log(total_pages / pages_with_word)
                total += tf * idf
        return total

    return sorted(urls, key=score, reverse=True)


def find_pages(index: IndexType, words: list[str]) -> tuple[list[str], list[str]]:
    """
    Return matching page URLs and any words that were missing from the index.

    Returns a tuple of (results, missing_words) so the caller can give a
    specific message for each outcome:
      - missing_words non-empty -> one or more words not in the index at all
      - results empty -> words exist but no page contains all of them
      - results non-empty -> pages found

    Case-insensitive: all words are lowercased before lookup.
    Multi-word: uses set intersection so every word must be on the page (AND).
    """
    # Case 2: empty query, caller should catch this before calling, but
    # guard here too so the function is safe to call independently
    if not words:
        return [], []

    # Case 3: mixed case, normalise to lowercase and deduplicate (preserving
    # order) so a word appearing twice does not inflate its TF-IDF score
    words = list(dict.fromkeys(w.lower() for w in words))

    # Case 1: word not in index: collect all missing words before returning
    # so the message can name exactly which word(s) weren't found
    missing = [w for w in words if w not in index]
    if missing:
        return [], missing

    # Case 4: multi-word query, intersect page sets so only pages containing
    # every word are returned
    page_sets = [set(index[w].keys()) for w in words]
    matching = page_sets[0].intersection(*page_sets[1:])
    return rank_results(index, list(matching), words), []


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

    # Case 1: word not in index, suggest close matches if any exist
    if word not in index:
        suggestions = suggest_words(index, word)
        if suggestions:
            print(f"'{word}' was not found in the index. Did you mean: {', '.join(suggestions)}?")
        else:
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
        Results for 'good friends' : 2 word(s), 1 page(s) found:

          https://quotes.toscrape.com/page/3/
    """
    # Case 2: empty query
    words = query.strip().split()
    if not words:
        print("Usage: find <word> [word2 ...]")
        return

    results, missing = find_pages(index, words)

    # Case 1: one or more words not in the index at all, suggest close
    # matches per missing word so the user knows what to try instead
    if missing:
        for w in missing:
            suggestions = suggest_words(index, w)
            if suggestions:
                print(f"'{w}' not found in the index. Did you mean: {', '.join(suggestions)}?")
            else:
                print(f"'{w}' not found in the index.")
        return

    # Case 4 (no overlap): words exist but no page contains all of them
    if not results:
        print(f"No pages contain all of: {', '.join(words)}")
        return

    # Success — show matching pages
    print(f"\nResults for '{query.strip()}' : {len(words)} word(s), {len(results)} page(s) found:\n")
    for url in results:
        print(f"  {url}")
    print()
