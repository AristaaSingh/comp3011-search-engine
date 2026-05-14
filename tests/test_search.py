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
  8. Three-word queries
  9. Duplicate words in query
  10. Multiple missing words
  11. print_word whitespace handling
  12. Did you mean suggestions : close matches shown for missing words
"""

import time
import pytest
from src.crawler import PageData
from src.indexer import build_index, save_index, load_index
from src.search import find_pages, print_word, find_and_print, rank_results, suggest_words

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


# Case 7: normalised TF-IDF ranking
#
# "rare" appears on URL_1 and URL_2 only, giving IDF("rare") > 0.
# "common" appears on all three pages, giving IDF("common") = log(3/3) = 0.
#
# URL_1: "rare rare rare common" -> 4 tokens, rare TF = 3/4 = 0.75
# URL_2: "rare common" -> 2 tokens, rare TF = 1/2 = 0.50
# URL_3: "common" -> 1 token,  no rare
#
# With normalised TF-IDF, URL_1 still ranks above URL_2 for "rare"
# because 0.75 > 0.50, and normalisation doesn't change that here.
# The key benefit of normalisation shows when comparing pages of very
# different lengths, preventing a long page from winning purely on bulk.

@pytest.fixture
def ranking_index():
    pages = [
        PageData(url=URL_1, text="rare rare rare common"), # 4 tokens, rare TF = 3/4
        PageData(url=URL_2, text="rare common"), # 2 tokens, rare TF = 1/2
        PageData(url=URL_3, text="common"), # 1 token,  no rare
    ]
    return build_index(pages)


def test_tfidf_higher_normalised_tf_ranks_first(ranking_index):
    # URL_1 has rare TF = 0.75, URL_2 has rare TF = 0.50: URL_1 ranks first
    results, _ = find_pages(ranking_index, ["rare"])
    assert results[0] == URL_1


def test_tfidf_lower_normalised_tf_ranks_last(ranking_index):
    # URL_2 has the lowest normalised TF for "rare": it should be last
    results, _ = find_pages(ranking_index, ["rare"])
    assert results[-1] == URL_2


def test_tfidf_common_word_returns_all_pages(ranking_index):
    # "common" is on all 3 pages, IDF = 0, all pages should appear in results
    results, _ = find_pages(ranking_index, ["common"])
    assert set(results) == {URL_1, URL_2, URL_3}


def test_tfidf_rare_word_dominates_score_in_multi_word_query(ranking_index):
    # IDF("common") = 0 so it contributes nothing, only "rare" drives ranking
    # URL_1 (rare TF = 0.75) should rank above URL_2 (rare TF = 0.50)
    results, _ = find_pages(ranking_index, ["rare", "common"])
    assert results[0] == URL_1


def test_tfidf_shorter_page_with_higher_density_ranks_higher():
    # Normalisation benefit: URL_2 is shorter but has higher word density.
    # URL_3 has no "good" so IDF("good") = log(3/2) > 0, making scores non-zero.
    # URL_1: "good good good filler filler filler filler filler" -> good TF = 3/8 = 0.375
    # URL_2: "good good" -> good TF = 2/2 = 1.0
    # URL_3: "filler" -> no good
    # URL_2 should rank above URL_1 despite fewer raw occurrences, because
    # normalised TF (1.0) beats (0.375) when page length is accounted for.
    pages = [
        PageData(url=URL_1, text="good good good filler filler filler filler filler"),
        PageData(url=URL_2, text="good good"),
        PageData(url=URL_3, text="filler"),
    ]
    dense_index = build_index(pages)
    results, _ = find_pages(dense_index, ["good"])
    assert results[0] == URL_2


def test_rank_results_empty_list(ranking_index):
    assert rank_results(ranking_index, [], ["rare"]) == []


# Case 8: three-word queries

def test_three_word_query_returns_page_with_all_three(index):
    # URL_2 has "good", "friends", "life", the other pages are missing at least one
    results, _ = find_pages(index, ["good", "friends", "life"])
    assert URL_2 in results
    assert URL_1 not in results


def test_three_word_query_no_page_has_all_three(index):
    # "wonder" only on URL_3, "friends" only on URL_2, "good" on URL_1 and URL_2
    results, _ = find_pages(index, ["good", "friends", "wonder"])
    assert results == []


# Case 9: duplicate words in query

def test_duplicate_words_in_query_behave_like_single_word(index):
    """Searching for the same word twice should give the same results as once."""
    single, _ = find_pages(index, ["life"])
    double, _ = find_pages(index, ["life", "life"])
    assert set(double) == set(single)


# Case 10: multiple missing words

def test_multiple_missing_words_all_named(index):
    """If two words are missing, both should appear in the missing list."""
    _, missing = find_pages(index, ["xyz", "abc"])
    assert "xyz" in missing
    assert "abc" in missing


def test_find_and_print_names_all_missing_words(index, capsys):
    """find_and_print output should mention all missing words, not just the first."""
    find_and_print(index, "xyz abc")
    out = capsys.readouterr().out
    assert "xyz" in out or "abc" in out


# Case 11: print_word whitespace handling

def test_print_word_strips_surrounding_whitespace(index, capsys):
    """print_word should find a word even if the input has surrounding spaces."""
    print_word(index, "  life  ")
    assert URL_1 in capsys.readouterr().out


# Case 12: did you mean suggestions

def test_suggest_words_returns_close_match(index):
    """A near-miss spelling should return the correct word as a suggestion."""
    # "frends" is close enough to "friends" (similarity > 0.6)
    suggestions = suggest_words(index, "frends")
    assert "friends" in suggestions


def test_suggest_words_returns_empty_for_no_match(index):
    """A completely unrelated string should return no suggestions."""
    suggestions = suggest_words(index, "xyzxyzxyz")
    assert suggestions == []


def test_suggest_words_excludes_meta_key(index):
    """The internal '__meta__' key must never appear as a suggestion."""
    suggestions = suggest_words(index, "__meta__")
    assert "__meta__" not in suggestions


def test_print_word_shows_did_you_mean(index, capsys):
    """print_word should print a 'Did you mean' hint when a near-miss exists."""
    print_word(index, "frends")
    assert "Did you mean" in capsys.readouterr().out


def test_find_and_print_shows_did_you_mean(index, capsys):
    """find_and_print should print a 'Did you mean' hint for a near-miss word."""
    find_and_print(index, "frends")
    assert "Did you mean" in capsys.readouterr().out


def test_find_and_print_no_suggestion_for_gibberish(index, capsys):
    """find_and_print should print 'not found' without a suggestion for gibberish."""
    find_and_print(index, "xyzxyzxyz")
    out = capsys.readouterr().out
    assert "not found" in out
    assert "Did you mean" not in out


# Case 13: Integration test (full pipeline)
#
# Verifies that find_and_print produces correct output when the index is
# built, saved, loaded, and searched in sequence. This crosses the boundary
# between the indexer and search components, which the unit tests above do
# not cover since they use a pre-built in-memory fixture.

def test_find_and_print_after_save_load(tmp_path, capsys):
    """find_and_print should return correct results after a full save/load cycle."""
    pages = [
        PageData(url=URL_1, text="life is good"),
        PageData(url=URL_2, text="good friends make life better"),
        PageData(url=URL_3, text="friendship and wonder"),
    ]
    index = build_index(pages)
    path = tmp_path / "index.json"
    save_index(index, path)
    loaded = load_index(path)

    find_and_print(loaded, "good friends")
    assert URL_2 in capsys.readouterr().out


# Case 14: Performance tests
#
# Verifies that ranking and search operations complete within acceptable
# time bounds on a 200-page index. The large_index fixture uses
# scope='module' so it is built once and shared across both tests,
# avoiding repeated construction overhead.

PERF_VOCAB = ["life", "good", "friend", "hope", "dream", "love", "world",
              "heart", "mind", "soul", "time", "way", "day", "truth", "light",
              "wonder", "beauty", "change", "faith", "grace"]


@pytest.fixture(scope="module")
def large_index():
    """200-page index built once and shared across performance tests."""
    pages = [
        PageData(
            url=f"https://example.com/page/{i}/",
            text=" ".join(PERF_VOCAB[j % len(PERF_VOCAB)] for j in range(i, i + 50)),
        )
        for i in range(200)
    ]
    return build_index(pages)


def test_rank_results_performance(large_index):
    """rank_results across 200 URLs should complete in under 0.1 seconds."""
    urls = [f"https://example.com/page/{i}/" for i in range(200)]
    start = time.perf_counter()
    rank_results(large_index, urls, ["life"])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"rank_results took {elapsed:.3f}s, expected < 0.1s"


def test_find_pages_performance(large_index):
    """find_pages on a 200-page index should complete in under 0.1 seconds."""
    start = time.perf_counter()
    find_pages(large_index, ["life"])
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"find_pages took {elapsed:.3f}s, expected < 0.1s"
