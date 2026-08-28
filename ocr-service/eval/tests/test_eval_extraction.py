"""Regression tests for the pre-resolver extraction metrics."""

from scripts.eval_extraction import fuzzy_score, match_one_to_one


def test_three_letter_drug_name_matches_an_exact_label_token():
    report = match_one_to_one(["JEX (H/30v)"], [["JEX"]])

    assert report["misses"] == []
    assert report["spurious"] == []
    assert report["fuzzy_hits"] == [("JEX (H/30v)", "JEX", 100.0)]


def test_short_text_is_not_fuzzy_matched_by_substring():
    assert fuzzy_score("Số toa", ["Số"]) == 0.0
    assert fuzzy_score("AJEXA", ["JEX"]) == 0.0
