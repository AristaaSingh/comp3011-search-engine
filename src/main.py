"""
main.py — Command-line interface for the search engine.

Supports four commands as specified in the brief:
    build               Crawl the site, build the index, save to disk
    load                Load a previously saved index from disk
    print <word>        Print the index entry for a word
    find <query>        Find pages containing all words in the query
"""

import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

from src.crawler import crawl_site
from src.indexer import build_index, save_index, load_index
from src.search import print_word, find_and_print


def run_shell() -> None:
    """Start the interactive command loop."""
    index = None

    print("Search Engine — type 'help' for available commands.\n")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "build":
            print("Crawling site — this will take a while (~20 mins, 6s between requests)...")
            print("Pages crawled so far will be shown as they are fetched.\n")
            pages = crawl_site()
            index = build_index(pages)
            save_index(index)
            print(f"Done. {len(pages)} page(s) crawled, {len(index)} unique word(s) indexed.")

        elif command == "load":
            try:
                index = load_index()
                print(f"Index loaded — {len(index)} unique word(s).")
            except FileNotFoundError as e:
                print(f"Error: {e}")

        elif command == "print":
            if index is None:
                print("No index loaded. Run 'build' or 'load' first.")
            elif not args:
                print("Usage: print <word>")
            else:
                print_word(index, args)

        elif command == "find":
            if index is None:
                print("No index loaded. Run 'build' or 'load' first.")
            elif not args:
                print("Usage: find <word> [word2 ...]")
            else:
                find_and_print(index, args)

        elif command == "help":
            print(
                "\nCommands:\n"
                "  build               Crawl the site, build and save the index\n"
                "  load                Load a saved index from disk\n"
                "  print <word>        Print index entry for a word\n"
                "  find <word(s)>      Find pages containing all given words\n"
                "  exit                Exit the shell\n"
            )

        elif command in ("exit", "quit"):
            print("Exiting.")
            break

        else:
            print(f"Unknown command '{command}'. Type 'help' for available commands.")


if __name__ == "__main__":
    run_shell()
