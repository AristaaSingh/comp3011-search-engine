"""
indexer.py — Builds and saves the inverted index.

Takes the list of PageData objects produced by the crawler and builds
an inverted index: a dictionary mapping every word to the pages it
appears on, along with how often and at what positions.

The index is saved and loaded as a JSON file so it is human-readable
and easy to inspect or submit alongside the code.
"""

import re
import json
import logging
from collections import defaultdict
from pathlib import Path

from src.crawler import PageData

logger = logging.getLogger(__name__)

INDEX_PATH = Path("data/index.json")

# Type alias for the inverted index structure:
#   word -> url -> { "frequency": int, "positions": list[int] }
IndexType = dict[str, dict[str, dict[str, int | list[int]]]]


def tokenise(text: str) -> list[str]:
    """
    Split a page's text into a list of individual word tokens.

    Uses a regex to extract only sequences of letters and apostrophes,
    which strips punctuation like commas and full stops so that 'life,'
    and 'life' are treated as the same word.

    Edge cases handled:
      - Empty string        → returns []
      - Punctuation only    → returns []  e.g. "!!!" → []
      - Mixed punctuation   → stripped    e.g. "hello!!!" → ["hello"]
      - Already lowercase   → no change   (crawler lowercases, but we do
                                           it here too for safety)
    """
    if not text:
        return []
    return re.findall(r"[a-z']+", text.lower())


def add_page_to_index(index: IndexType, page: PageData) -> None:
    """
    Index a single page into an existing index dictionary.

    Tokenises the page text and, for each word, records the page URL,
    running frequency count, and every position the word appears at.

    Uses defaultdict internally so there is no need to manually check
    whether a word or URL key exists before writing to it.

    Modifies the index dict in place — nothing is returned.

    Edge cases handled:
      - Empty page text     → tokenise returns [], loop is skipped, no crash
      - Very little content → works fine, just produces fewer index entries
      - Repeated words      → frequency increments and each position is recorded
    """
    tokens = tokenise(page.text)

    if not tokens:
        logger.warning("No tokens found for %s — page may be empty", page.url)
        return

    for position, word in enumerate(tokens):
        # defaultdict auto-creates missing word and URL entries,
        # removing the need for manual existence checks
        entry = index[word][page.url]
        entry["frequency"] += 1
        entry["positions"].append(position)

    logger.info("Indexed %s (%d tokens)", page.url, len(tokens))


def build_index(pages: list[PageData]) -> IndexType:
    """
    Build the inverted index from a list of crawled pages.

    Delegates the per-page work to add_page_to_index, keeping this
    function focused on orchestration only.

    Uses a nested defaultdict so entries are created automatically
    on first access — no manual key checks needed.

    The resulting structure looks like:
        {
            "life": {
                "https://quotes.toscrape.com/": {
                    "frequency": 3,
                    "positions": [4, 27, 61]
                },
                "https://quotes.toscrape.com/page/2/": {
                    "frequency": 1,
                    "positions": [12]
                }
            },
            ...
        }
    """
    # Nested defaultdict: word -> url -> {"frequency": 0, "positions": []}
    # Each missing key at any level is auto-initialised on first access
    index: IndexType = defaultdict(
        lambda: defaultdict(lambda: {"frequency": 0, "positions": []})
    )

    for page in pages:
        add_page_to_index(index, page)

    logger.info("Index built. Total unique words: %d", len(index))
    return index


def save_index(index: IndexType, path: Path = INDEX_PATH) -> None:
    """
    Save the index to a JSON file.

    Converts the defaultdict to a plain dict before serialising so the
    JSON file contains no defaultdict-specific metadata.
    Creates the data/ directory if it does not already exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # json.dump handles defaultdict fine (it's a dict subclass),
        # but we cast explicitly to make the intent clear
        json.dump({k: dict(v) for k, v in index.items()}, f, indent=2)
    logger.info("Index saved to %s", path)


def load_index(path: Path = INDEX_PATH) -> IndexType:
    """
    Load and return the index from a JSON file.

    Validates that the loaded data has the expected structure before
    returning it, catching corrupted or incompatible index files early.

    Raises:
      FileNotFoundError  — index file does not exist (run 'build' first)
      ValueError         — file exists but does not contain a valid index
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No index file found at '{path}'. Run 'build' first."
        )

    with open(path, "r", encoding="utf-8") as f:
        index = json.load(f)

    _validate_index(index)

    logger.info("Index loaded from %s (%d unique words)", path, len(index))
    return index


def _validate_index(index: object) -> None:
    """
    Check that a loaded index has the expected structure.

    Expected format:
        { word(str): { url(str): { "frequency": int, "positions": list } } }

    Raises ValueError with a descriptive message if anything looks wrong.
    Samples the first entry only — checking every word would be slow on
    large indexes and offers little extra safety.
    """
    if not isinstance(index, dict):
        raise ValueError("Index file is invalid: expected a JSON object at the top level.")

    # Sample the first word entry to verify the nested structure
    for word, pages in index.items():
        if not isinstance(pages, dict):
            raise ValueError(f"Index file is invalid: entry for '{word}' should be a dict.")
        for url, stats in pages.items():
            if not isinstance(stats, dict):
                raise ValueError(f"Index file is invalid: stats for '{url}' should be a dict.")
            if "frequency" not in stats or "positions" not in stats:
                raise ValueError(
                    f"Index file is invalid: stats for '{url}' missing 'frequency' or 'positions'."
                )
        break  # one sample is enough
