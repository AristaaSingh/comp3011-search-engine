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


def build_index(pages: list[PageData]) -> dict:
    """
    Build the inverted index from a list of crawled pages.

    For every word on every page, we record:
      - frequency : total number of times the word appears on that page
      - positions : list of positions (0-based) where the word appears
                    in the token list for that page

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
        tokens = tokenise(page.text)

        for position, word in enumerate(tokens):
            # Create entry for word if it does not exist yet
            if word not in index:
                index[word] = {}

            # Create entry for this page under the word if not yet seen
            if page.url not in index[word]:
                index[word][page.url] = {"frequency": 0, "positions": []}

            # Update frequency and record this position
            index[word][page.url]["frequency"] += 1
            index[word][page.url]["positions"].append(position)

        logger.info("Indexed %s (%d tokens)", page.url, len(tokens))

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
