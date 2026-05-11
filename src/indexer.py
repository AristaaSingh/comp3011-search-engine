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
from pathlib import Path

from src.crawler import PageData

logger = logging.getLogger(__name__)

INDEX_PATH = Path("data/index.json")


def tokenise(text: str) -> list[str]:
    """
    Split a page's text into a list of individual word tokens.

    Uses a regex to extract only sequences of letters and apostrophes,
    which strips punctuation like commas and full stops so that 'life,'
    and 'life' are treated as the same word.

    The text coming from the crawler is already lowercase, but we
    apply .lower() here too so the function works independently.
    """
    return re.findall(r"[a-z']+", text.lower())


def add_page_to_index(index: dict, page: PageData) -> None:
    """
    Index a single page into an existing index dictionary.

    Tokenises the page text and, for each word, records the page URL,
    running frequency count, and every position the word appears at.

    Modifies the index dict in place — nothing is returned.
    """
    tokens = tokenise(page.text)

    for position, word in enumerate(tokens):
        # Create entry for this word if it does not exist yet
        if word not in index:
            index[word] = {}

        # Create entry for this page under the word if not yet seen
        if page.url not in index[word]:
            index[word][page.url] = {"frequency": 0, "positions": []}

        # Update frequency and record this position
        index[word][page.url]["frequency"] += 1
        index[word][page.url]["positions"].append(position)

    logger.info("Indexed %s (%d tokens)", page.url, len(tokens))


def build_index(pages: list[PageData]) -> dict:
    """
    Build the inverted index from a list of crawled pages.

    Delegates the per-page work to add_page_to_index, keeping this
    function focused on orchestration only.

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
    index = {}

    for page in pages:
        add_page_to_index(index, page)

    logger.info("Index built. Total unique words: %d", len(index))
    return index


def save_index(index: dict, path: Path = INDEX_PATH) -> None:
    """
    Save the index dictionary to a JSON file.

    Creates the data/ directory if it does not already exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    logger.info("Index saved to %s", path)


def load_index(path: Path = INDEX_PATH) -> dict:
    """
    Load and return the index from a JSON file.

    Raises FileNotFoundError with a helpful message if the file does
    not exist yet — i.e. 'build' has not been run.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No index file found at '{path}'. Run 'build' first."
        )
    with open(path, "r", encoding="utf-8") as f:
        index = json.load(f)
    logger.info("Index loaded from %s (%d unique words)", path, len(index))
    return index
