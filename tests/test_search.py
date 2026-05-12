"""
test_search.py: Tests for search.py

Covers the four explicitly handled cases:
  1. Word not found : missing word returned, results empty
  2. Empty query : returns empty with no crash
  3. Mixed case : Good == good, LIFE == life
  4. Multi-word query : AND logic, all words must be on the page

Plus:
  5. Exact word match : 'friends' does not return pages with 'friendship'
  6. Output : print_word and find_and_print message correctness
  7. Ranking : higher frequency pages appear first in results
"""

import pytest
from src.crawler import PageData
from src.indexer import build_index
from src.search import find_pages, print_word, find_and_print, rank_results

URL_1 = "https://quotes.toscrape.com/"
URL_2 = "https://quotes.toscrape.com/page/2/"
URL_3 = "https://quotes.toscrape.com/page/3/"


@pytest.fixture
def index():
    pages = [
        PageData(url=URL_1, text="life is good"),
        PageData(url=URL_2, text="good friends make life better"),
        PageData(url=URL_3, text="friendship and wonder"),
    ]
    return build_index(pages)


# Case 1: word not found

def test_missing_word_returns_empty_results(index):
    results, missing = find_pages(index, ["nonsense"])
    assert results == []

def test_missing_word_is_named_in_missing_list(index):
    results, missing = find_pages(index, ["nonsense"])
    assert "nonsense" in missing

def test_one_missing_word_in_multi_word_query(index):
    # "life" exists but "xyz" does not, missing should name "xyz"
    results, missing = find_pages(index, ["life", "xyz"])
    assert results == []
    assert "xyz" in missing

def test_find_and_print_names_missing_word(index, capsys):
    find_and_print(index, "nonsense")
    assert "not found" in capsys.readouterr().out


# Case 2: empty query

def test_empty_word_list_returns_empty(index):
    results, missing = find_pages(index, [])
    assert results == []
    assert missing == []

def test_empty_string_query_prints_usage(index, capsys):
    find_and_print(index, "")
    assert "Usage" in capsys.readouterr().out

def test_whitespace_only_query_prints_usage(index, capsys):
    find_and_print(index, "   ")
    assert "Usage" in capsys.readouterr().out


# Case 3: mixed case

def test_uppercase_finds_same_pages_as_lowercase(index):
    lower_results, _ = find_pages(index, ["life"])
    upper_results, _ = find_pages(index, ["LIFE"])
    assert lower_results == upper_results

def test_mixed_case_finds_correct_pages(index):
    results, _ = find_pages(index, ["Good"])
    assert URL_1 in results
    assert URL_2 in results

def test_all_caps_multi_word_query(index):
    results, _ = find_pages(index, ["GOOD", "FRIENDS"])
    assert results == [URL_2]


# Case 4: multi-word query (AND logic)

def test_multi_word_returns_only_pages_with_all_words(index):
    # "good" is on URL_1 and URL_2, "friends" is only on URL_2
    results, _ = find_pages(index, ["good", "friends"])
    assert results == [URL_2]

def test_multi_word_no_overlap_returns_empty(index):
    # "wonder" is on URL_3, "friends" is on URL_2 : no page has both
    results, _ = find_pages(index, ["wonder", "friends"])
    assert results == []

def test_multi_word_no_overlap_prints_specific_message(index, capsys):
    find_and_print(index, "wonder friends")
    assert "No pages contain all of" in capsys.readouterr().out

def test_single_word_query_returns_all_matching_pages(index):
    results, _ = find_pages(index, ["life"])
    assert URL_1 in results
    assert URL_2 in results


# Case 5: exact word match

def test_friends_does_not_return_friendship_page(index):
    # URL_3 has "friendship" : searching "friends" must not return it
    results, _ = find_pages(index, ["friends"])
    assert URL_3 not in results

def test_friendship_does_not_return_friends_page(index):
    # URL_2 has "friends" : searching "friendship" must not return it
    results, _ = find_pages(index, ["friendship"])
    assert URL_2 not in results

def test_exact_match_returns_correct_page(index):
    results, _ = find_pages(index, ["friendship"])
    assert results == [URL_3]


# Case 6: print_word output

def test_print_word_shows_url(index, capsys):
    print_word(index, "life")
    assert URL_1 in capsys.readouterr().out

def test_print_word_shows_frequency(index, capsys):
    print_word(index, "life")
    assert "frequency" in capsys.readouterr().out

def test_print_word_shows_positions(index, capsys):
    print_word(index, "life")
    assert "positions" in capsys.readouterr().out

def test_print_word_not_in_index(index, capsys):
    print_word(index, "nonsense")
    assert "not found" in capsys.readouterr().out

def test_print_word_empty_input(index, capsys):
    print_word(index, "")
    assert "Usage" in capsys.readouterr().out

def test_print_word_case_insensitive(index, capsys):
    print_word(index, "LIFE")
    assert URL_1 in capsys.readouterr().out


# Case 7: ranking

@pytest.fixture
def ranking_index():
    """Index where URL_1 has higher frequency of the query word than URL_2."""
    pages = [
        PageData(url=URL_1, text="good good good life"), # good*3, life*1 -> score 4
        PageData(url=URL_2, text="good life life life"), # good*1, life*3 -> score 4 (tie)
        PageData(url=URL_3, text="good life"), # good*1, life*1 -> score 2
    ]
    return build_index(pages)

def test_rank_results_higher_frequency_first(ranking_index):
    # URL_3 has the lowest combined frequency for "good life" : must be last
    results, _ = find_pages(ranking_index, ["good", "life"])
    assert results[-1] == URL_3

def test_rank_results_lowest_frequency_last(ranking_index):
    results, _ = find_pages(ranking_index, ["good", "life"])
    scores = [
        ranking_index["good"][url]["frequency"] + ranking_index["life"][url]["frequency"]
        for url in results
    ]
    # Scores should be in descending order
    assert scores == sorted(scores, reverse=True)

def test_rank_results_single_word(ranking_index):
    # "good" appears 3x on URL_1, 1x on URL_2 and URL_3 : URL_1 should rank first
    results, _ = find_pages(ranking_index, ["good"])
    assert results[0] == URL_1

def test_rank_results_empty_list(ranking_index):
    assert rank_results(ranking_index, [], ["good"]) == []
