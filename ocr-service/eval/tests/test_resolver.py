"""Text normalization, strength extraction and drug resolver tests."""

from __future__ import annotations

import time

import pytest

from app.config import Settings
from app.services.drug_resolver import CsvDrugRepository, Drug, DrugResolver
from app.utils.text_utils import (
    bare_name_numbers,
    confusion_fold,
    extract_strengths,
    line_windows,
    matching_key,
    normalize_text,
    strength_keys,
    strength_numbers,
    strip_diacritics,
)


@pytest.fixture
def resolver(sample_csv) -> DrugResolver:
    instance = DrugResolver(sample_csv)
    instance.load()
    return instance


def names(result: dict) -> list[str]:
    return [c["drug_name"] for c in result["candidates"]]


# --------------------------------------------------------------------------
# Text normalization
# --------------------------------------------------------------------------


def test_normalize_collapses_whitespace_and_line_breaks():
    assert normalize_text("  HAPAC0L \r\n\r\n   65O   ") == "HAPAC0L\n65O"


def test_normalize_handles_unicode_and_punctuation():
    assert normalize_text("Ｈapacol – 650") == "Hapacol - 650"


def test_normalize_preserves_case_but_matching_key_folds_it():
    assert normalize_text("HAPACOL") == "HAPACOL"
    assert matching_key("HAPACOL") == "hapacol"


def test_confusion_fold_makes_ocr_errors_comparable():
    """The fold is applied to both sides; neither string is rewritten."""
    assert confusion_fold("HAPAC0L 65O") == confusion_fold("Hapacol 650")
    assert confusion_fold("AUGMENTlN") == confusion_fold("Augmentin")
    assert confusion_fold("5ANDOZ") == confusion_fold("Sandoz")


def test_confusion_fold_does_not_merge_unrelated_drugs():
    assert confusion_fold("Hapacol 650") != confusion_fold("Hapacol 250")


@pytest.mark.parametrize(
    ("ocr", "database"),
    [
        ("Long huyét P/H extra", "Long huyết P/H extra"),
        ("Giam dau - Ha söt", "Giảm đau - Hạ sốt"),
        ("Khòng gày buòn ngú", "Không gây buồn ngủ"),
        ("Vièn nén bao phim", "Viên nén bao phim"),
        ("Thuoc nho mat", "Thuốc nhỏ mắt"),
    ],
)
def test_vietnamese_tone_marks_are_folded_for_matching(ocr, database):
    """OCR mangles tone marks; they carry no identifying information."""
    assert confusion_fold(ocr) == confusion_fold(database)


def test_d_stroke_folds_to_d():
    """U+0111 has no combining form, so NFD alone would not fold it."""
    assert strip_diacritics("đau đầu") == "dau dau"
    assert strip_diacritics("Đông dược") == "Dong duoc"


def test_diacritic_folding_does_not_reach_displayed_text():
    """normalize_text is user-facing and must keep Vietnamese readable."""
    assert normalize_text("Giảm đau - Hạ sốt") == "Giảm đau - Hạ sốt"


# --------------------------------------------------------------------------
# Strength extraction (Phase 7)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("500 mg", ["500 mg"]),
        ("650mg", ["650 mg"]),
        ("5 mg", ["5 mg"]),
        ("125 mg/5 ml", ["125 mg/5 ml"]),
        ("500 mg / 125 mg", ["500 mg/125 mg"]),
        ("10 mg/ml", ["10 mg/ml"]),
        ("0.5%", ["0.5%"]),
        ("1000 IU", ["1000 IU"]),
        ("0,5%", ["0.5%"]),
        ("Vitamin D3 400 UI", ["400 IU"]),
    ],
)
def test_extract_strengths_patterns(text, expected):
    assert extract_strengths(text) == expected


def test_extract_strengths_from_multiline_ocr_text():
    text = "AUGMENTIN 625mg\nAmoxicillin 500 mg\nClavulanic acid 125 mg"
    assert extract_strengths(text) == ["625 mg", "500 mg", "125 mg"]


def test_extract_strengths_ignores_plain_numbers():
    assert extract_strengths("Hapacol 650") == []
    assert extract_strengths("Lot 12345 EXP 2027") == []


def test_extract_strengths_does_not_match_inside_a_word():
    """Regression: "HAPAC0L" used to yield "0 L" (zero litres)."""
    assert extract_strengths("HAPAC0L 65O") == []
    assert extract_strengths("PANAD0L") == []
    # A unit must be a whole token, not the start of a longer word.
    assert extract_strengths("Hop 10 vi x 10 vien") == []
    assert extract_strengths("500 mgX") == []


def test_extract_strengths_still_matches_at_token_boundaries():
    assert extract_strengths("HAPACOL 650mg") == ["650 mg"]
    assert extract_strengths("(500 mg)") == ["500 mg"]
    assert extract_strengths("Dung dich 10 ml") == ["10 ml"]


def test_strength_numbers_normalizes_for_comparison():
    assert strength_numbers("650 mg") == {"650"}
    assert strength_numbers("500 mg + 125 mg") == {"500", "125"}
    assert strength_numbers("2.50 mg") == {"2.5"}


def test_strength_keys_are_unit_aware_and_convert_equivalent_masses():
    assert strength_keys("1 g") == strength_keys("1000 mg") == {"mass:1000"}
    assert strength_keys("1 g") != strength_keys("1 mg")


def test_ratio_strength_keeps_mass_and_volume_dimensions_separate():
    assert strength_keys("500 mg/5 ml") == {"mass:500", "volume:5"}
    assert strength_keys("500 mg + 5 mg") == {"mass:500", "mass:5"}


def test_only_unitless_product_numbers_become_strength_aliases():
    assert bare_name_numbers("Augmentin 625") == {"625"}
    assert bare_name_numbers("Example 1 g") == set()


# --------------------------------------------------------------------------
# Candidate generation (Phase 5)
# --------------------------------------------------------------------------


def test_line_windows_joins_consecutive_lines():
    windows = line_windows(["HAPAC0L", "65O", "Paracetamol"], max_window=3)

    assert "HAPAC0L" in windows
    assert "HAPAC0L 65O" in windows
    assert "HAPAC0L 65O Paracetamol" in windows
    # Non-adjacent lines are never glued together.
    assert "HAPAC0L Paracetamol" not in windows


def test_line_windows_respects_max_window():
    windows = line_windows(["a", "b", "c", "d"], max_window=2)
    assert "a b c" not in windows


# --------------------------------------------------------------------------
# Repository
# --------------------------------------------------------------------------


def test_csv_repository_loads_canonical_schema(sample_csv):
    drugs = CsvDrugRepository(sample_csv).load()

    assert len(drugs) >= 6
    hapacol = next(d for d in drugs if d.drug_name == "Hapacol 650")
    assert hapacol.active_ingredient == "Paracetamol"
    assert hapacol.strength == "650 mg"
    assert hapacol.manufacturer == "DHG Pharma"


def test_missing_database_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        CsvDrugRepository(tmp_path / "nope.csv").load()


def test_repository_is_swappable_without_touching_the_resolver():
    """Any object with `.load() -> list[Drug]` works: CSV today, SQL later."""

    class InMemoryRepository:
        def load(self):
            return [Drug(id="99", drug_name="Testamol 500", active_ingredient="Paracetamol", strength="500 mg")]

    resolver = DrugResolver(InMemoryRepository())
    result = resolver.resolve(["TESTAM0L", "500mg"])

    assert result["candidates"][0]["drug_id"] == "99"


def test_longer_exact_brand_wins_when_scores_and_position_are_tied():
    class InMemoryRepository:
        def load(self):
            return [
                Drug(id="1", drug_name="Augmex"),
                Drug(id="2", drug_name="Augmex Duo"),
            ]

    resolver = DrugResolver(InMemoryRepository())
    result = resolver.resolve(["AUGMEX DUO 1G"])

    assert result["candidates"][0]["drug_name"] == "Augmex Duo"


def test_short_brand_with_one_missing_glyph_survives_pack_text_shortlist():
    class InMemoryRepository:
        def load(self):
            return [
                Drug(id="1", drug_name="Atussin", active_ingredient="Dextromethorphan"),
                Drug(id="2", drug_name="Dextromethorphan", active_ingredient="Dextromethorphan"),
            ]

    resolver = DrugResolver(InMemoryRepository())
    result = resolver.resolve([
        "Aussin SR 60ml (hết hàng)",
        "Dextromethorphan, chlopheniramin",
    ])

    assert "Atussin" in names(result)


def test_registry_csv_layout_is_supported(tmp_path):
    path = tmp_path / "registry.csv"
    path.write_text(
        "Ten_thuoc,Hoat_chat_list,So_hoat_chat\n"
        '"Hapacol 650","[{""ten"": ""Paracetamol""}]",1\n',
        encoding="utf-8",
    )
    drugs = CsvDrugRepository(path).load()

    assert drugs[0].drug_name == "Hapacol 650"
    assert drugs[0].active_ingredient == "Paracetamol"
    assert drugs[0].strength == ""  # "650" alone carries no unit


# --------------------------------------------------------------------------
# Required matching cases
# --------------------------------------------------------------------------


def test_hapacol_ocr_errors_resolve_to_hapacol_650(resolver):
    """Mandated case: "HAPAC0L 65O" -> "Hapacol 650" at the top."""
    result = resolver.resolve(["HAPAC0L 65O"])
    assert result["candidates"][0]["drug_name"] == "Hapacol 650"


def test_hapacol_split_across_two_lines(resolver):
    """The name and the dose arrive as separate OCR regions."""
    result = resolver.resolve(["HAPAC0L", "65O", "Paracetamol", "650mg"])

    assert result["candidates"][0]["drug_name"] == "Hapacol 650"
    assert "650 mg" in result["strengths"]
    assert "Paracetamol" in result["possible_ingredients"]


def test_augmentin_strength_outranks_other_pack_sizes(resolver):
    """Mandated case: 625 must beat 1g when the image shows 625 mg."""
    result = resolver.resolve(["AUGMENTlN", "625 mg", "Amoxicillin"])
    ranked = names(result)

    assert ranked[0] == "Augmentin 625"
    assert ranked.index("Augmentin 625") < ranked.index("Augmentin 1g")


def test_augmentin_1g_wins_when_the_image_says_1g(resolver):
    """The strength signal must cut both ways, not just favour 625."""
    result = resolver.resolve(["AUGMENTIN", "875 mg", "125 mg", "Amoxicillin"])
    assert result["candidates"][0]["drug_name"] == "Augmentin 1g"


def test_top_three_candidates_at_most(resolver):
    result = resolver.resolve(["Hapacol"])
    assert len(result["candidates"]) <= 3


def test_scores_are_normalized_and_broken_down(resolver):
    candidate = resolver.resolve(["HAPAC0L 65O", "Paracetamol"])["candidates"][0]

    assert 0.0 <= candidate["score"] <= 1.0
    breakdown = candidate["score_breakdown"]
    assert set(breakdown) == {"name_score", "strength_score", "ingredient_score"}


def test_weighted_score_matches_the_configured_formula(sample_csv):
    config = Settings()
    resolver = DrugResolver(sample_csv, config=config)
    candidate = resolver.resolve(["HAPAC0L 65O", "Paracetamol"])["candidates"][0]
    parts = candidate["score_breakdown"]

    expected = (
        parts["name_score"] * config.weight_name
        + parts["strength_score"] * config.weight_strength
        + parts["ingredient_score"] * config.weight_ingredient
    )
    # `resolve` adds a flat +0.02 when the drug's whole name appears verbatim in
    # the OCR line, so an exact brand hit beats a fuzzy match on a related
    # product. It is deliberately outside the weighted formula -- the weights
    # stay a clean convex combination of the three breakdown parts. "HAPAC0L
    # 65O" folds onto "Hapacol 650" exactly, so the bonus applies here.
    assert candidate["score"] == pytest.approx(expected + 0.02, abs=1e-4)


def test_ingredient_signal_recovers_an_unreadable_brand(resolver):
    """A smudged brand name should still surface via the ingredient list."""
    result = resolver.resolve(["#$%&", "Clopidogrel", "75 mg"])
    assert "Plavix 75" in names(result)


def test_one_glyph_ingredient_error_recovers_the_matching_brand():
    class Repository:
        def load(self):
            return [
                Drug(
                    id="1",
                    drug_name="Spetcefy-200",
                    active_ingredient="Cefpodoxime",
                    strength="200 mg",
                ),
                Drug(
                    id="2",
                    drug_name="Vilerm 200mg tablet",
                    active_ingredient="Cefpodoxime",
                    strength="200 mg",
                ),
                Drug(
                    id="3",
                    drug_name="Cefpodoxime 200mg",
                    active_ingredient="Cefpodoxime",
                    strength="200 mg",
                ),
                Drug(
                    id="4",
                    drug_name="Dipesalox 200mg",
                    active_ingredient="Cefpodoxime",
                    strength="200 mg",
                ),
            ]

    resolver = DrugResolver(Repository())
    result = resolver.resolve(["Spetcely 200mg (Cetpodoxime)"])

    assert result["possible_ingredients"] == ["Cefpodoxime"]
    assert result["candidates"][0]["drug_name"] == "Spetcefy-200"


# --------------------------------------------------------------------------
# Status / confidence rules
# --------------------------------------------------------------------------


def test_clean_read_is_not_uncertain(resolver):
    result = resolver.resolve(["Hapacol 650", "Paracetamol", "650 mg"])
    assert result["status"] in {"high_confidence", "medium_confidence"}
    assert result["candidates"][0]["score"] >= 0.75


def test_garbage_text_is_uncertain(resolver):
    result = resolver.resolve(["zzzz", "qqqq wwww"])
    assert result["status"] == "uncertain"


def test_empty_ocr_returns_no_candidates(resolver):
    result = resolver.resolve([])

    assert result["candidates"] == []
    assert result["status"] == "uncertain"


def test_status_thresholds_follow_config(resolver):
    assert resolver.status_for(0.95) == "high_confidence"
    assert resolver.status_for(0.80) == "medium_confidence"
    assert resolver.status_for(0.74) == "uncertain"


def test_exact_name_containment_requires_token_boundaries():
    assert DrugResolver._name_position("xxxx hapacoi 6so", "hapacoi 6so") == 5
    assert DrugResolver._name_position("superoresolplus", "oresol") is None


# --------------------------------------------------------------------------
# Performance
# --------------------------------------------------------------------------


def test_resolver_stays_within_latency_budget(resolver):
    lines = ["HAPAC0L", "65O", "Paracetamol 650mg", "DHG Pharma", "Hop 10 vi x 10 vien"]

    resolver.resolve(lines)  # warm up before timing
    started = time.perf_counter()
    for _ in range(10):
        resolver.resolve(lines)
    average_ms = (time.perf_counter() - started) * 1000 / 10

    assert average_ms < 100, f"resolver averaged {average_ms:.1f} ms"


def test_resolver_scales_to_a_large_database():
    """Shortlist-then-rerank must keep cost sub-linear in database size.

    Scoring every row with the expensive scorer took ~160 ms at this size,
    which is why the recall pass uses cheap scorers.
    """
    drugs = [
        Drug(id=str(i), drug_name=f"Testdrug{i} {i % 900} mg", active_ingredient="Paracetamol")
        for i in range(40_000)
    ]

    class BulkRepository:
        def load(self):
            return drugs

    resolver = DrugResolver(BulkRepository())
    resolver.load()
    lines = ["TESTDRUG7OO", "700 mg", "Paracetamol"]  # note the OCR'd letter O
    resolver.resolve(lines)  # warm up

    started = time.perf_counter()
    result = resolver.resolve(lines)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < 100, f"resolver took {elapsed_ms:.1f} ms on 40k rows"
    # The right row must survive the shortlist, not just be scored quickly.
    assert result["candidates"][0]["drug_name"] == "Testdrug700 700 mg"


def test_brand_at_the_front_of_a_row_outranks_the_generic_behind_it(sample_csv):
    """A prescription row names the brand first and the ingredient in brackets.

    Both match exactly and score name=1.00, so before the position tie-break
    the winner was decided by CSV row order: the database holds "Yesom 40" and
    returned "Esomeprazol 40" instead. Measured over six real prescription
    rows, this took the resolver from 3/6 to 6/6.
    """
    import csv as _csv
    import tempfile
    from pathlib import Path

    # A two-row database reproducing the tie: brand and generic, same strength,
    # same ingredient.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "drugs.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["Ten_thuoc", "Hoat_chat_list", "So_hoat_chat", "Is_Duoc_Lieu"])
            ingredient = '[{"ten": "Esomeprazole", "ddinter_id": "DDInter676"}]'
            writer.writerow(["Esomeprazol 40", ingredient, 1, False])
            writer.writerow(["Yesom 40", ingredient, 1, False])

        resolver = DrugResolver(path)
        candidates = resolver.resolve(["YESOM 40 40mg (Esomeprazol 40mg)"])["candidates"]

        assert candidates[0]["drug_name"] == "Yesom 40"
        # Yesom is a whole token at the front. The generic is embedded in a
        # longer ``Esomeprazol 40mg`` token, so it remains a weaker alternative.
        assert candidates[0]["score"] > candidates[1]["score"]


def test_position_tie_break_does_not_override_a_better_score(sample_csv):
    """It breaks ties only -- a genuinely better match still wins from behind."""
    resolver = DrugResolver(sample_csv)
    # "Hapacol 650" appears later in the line than the noise word in front of it.
    candidates = resolver.resolve(["xxxx Hapacol 650"])["candidates"]
    assert candidates[0]["drug_name"].lower().startswith("hapacol")
