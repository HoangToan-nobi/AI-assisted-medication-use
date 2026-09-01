"""Drug resolver: turns noisy OCR lines into ranked database candidates.

Pipeline
--------
1. Build candidate phrases from windows of consecutive OCR lines, so a brand
   name printed across two lines ("HAPAC0L" / "65O") can still match one row.
2. Score every phrase against every drug name with cheap RapidFuzz scorers,
   comparing OCR-confusion folds so "HAPAC0L" and "Hapacol" agree, and keep a
   shortlist.
3. Rerank the shortlist with the expensive scorer, blending three signals:

       final = name * W_name + strength * W_strength + ingredient * W_ingredient

The resolver only ever *proposes*. Selecting the drug is the user's job, and
nothing here feeds an interaction engine directly.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol, Sequence

import numpy as np
from rapidfuzz import fuzz, process

from app.config import Settings, settings as default_settings
from app.utils.text_utils import (
    bare_name_numbers,
    confusion_fold,
    extract_strengths,
    line_windows,
    matching_key,
    strength_keys,
    unique,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Drug:
    """One row of the drug database."""

    id: str
    drug_name: str
    active_ingredient: str = ""
    strength: str = ""
    dosage_form: str = ""
    manufacturer: str = ""
    registration_number: str = ""

    def ingredients(self) -> list[str]:
        """Split a combination ingredient string into its components."""
        parts = self.active_ingredient.replace(";", "+").replace(",", "+").split("+")
        return [part.strip() for part in parts if part.strip()]


class DrugRepository(Protocol):
    """Source of drug rows.

    Swapping the CSV for PostgreSQL means writing another implementation of
    this protocol -- neither ``DrugResolver`` nor ``OCRService`` changes.
    """

    def load(self) -> list[Drug]: ...


class CsvDrugRepository:
    """Loads drugs from a CSV file.

    Understands two layouts: the canonical schema documented in the README,
    and the ``Ten_thuoc`` / ``Hoat_chat_list`` export of the Vietnamese drug
    registry, so a real dataset can be dropped in without a conversion step.
    """

    CANONICAL_FIELDS = (
        "id",
        "drug_name",
        "active_ingredient",
        "strength",
        "dosage_form",
        "manufacturer",
        "registration_number",
    )

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[Drug]:
        if not self.path.exists():
            raise FileNotFoundError(f"Drug database not found: {self.path}")

        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if "Ten_thuoc" in fieldnames:
                rows = [self._from_registry_row(i, r) for i, r in enumerate(reader, 1)]
            else:
                rows = [self._from_canonical_row(i, r) for i, r in enumerate(reader, 1)]

        drugs = [drug for drug in rows if drug.drug_name]
        logger.info("Loaded %d drugs from %s", len(drugs), self.path)
        return drugs

    @classmethod
    def _from_canonical_row(cls, index: int, row: dict[str, str]) -> Drug:
        values = {key: (row.get(key) or "").strip() for key in cls.CANONICAL_FIELDS}
        return Drug(**{**values, "id": values["id"] or str(index)})

    @staticmethod
    def _from_registry_row(index: int, row: dict[str, str]) -> Drug:
        """Adapt a ``Ten_thuoc,Hoat_chat_list,...`` registry export."""
        ingredients: list[str] = []
        payload = row.get("Hoat_chat_list") or row.get("Hoat_chat") or ""
        if payload.strip().startswith("["):
            try:
                for item in json.loads(payload):
                    name = str(item.get("ten", "")).strip() if isinstance(item, dict) else ""
                    if name:
                        ingredients.append(name)
            except (ValueError, TypeError, AttributeError):
                pass
        elif payload.strip():
            ingredients.append(payload.strip())

        drug_name = (row.get("Ten_thuoc") or "").strip()
        return Drug(
            id=str(index),
            drug_name=drug_name,
            active_ingredient=" + ".join(ingredients),
            # The registry has no strength column; the name usually carries it.
            strength=" + ".join(extract_strengths(drug_name)),
            dosage_form=(row.get("Dang_bao_che") or "").strip(),
            manufacturer=(row.get("Nha_san_xuat") or "").strip(),
            registration_number=(row.get("So_dang_ky") or "").strip(),
        )


@dataclass
class _DrugIndex:
    """Precomputed comparison keys, built once at startup."""

    folded_names: list[str] = field(default_factory=list)
    name_numbers: list[set[str]] = field(default_factory=list)
    strength_keys: list[set[str]] = field(default_factory=list)
    folded_ingredients: list[list[str]] = field(default_factory=list)
    # Distinct ingredient vocabulary -> display form, for `possible_ingredients`.
    ingredient_vocab: dict[str, str] = field(default_factory=dict)


# Sorts last: the name was never found verbatim in the OCR line.
_NO_NAME_MATCH = 1 << 30


class DrugResolver:
    """Fuzzy-matches OCR output against the drug database."""

    def __init__(
        self,
        repository: DrugRepository | str | Path | None = None,
        config: Settings | None = None,
    ) -> None:
        self.settings = config or default_settings
        if repository is None:
            repository = CsvDrugRepository(self.settings.drugs_csv_path)
        elif isinstance(repository, (str, Path)):
            repository = CsvDrugRepository(repository)

        self.repository = repository
        self.drugs: list[Drug] = []
        self._index = _DrugIndex()
        self._loaded = False

    # -- lifecycle ---------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return self._loaded and bool(self.drugs)

    def load(self) -> None:
        self.drugs = self.repository.load()
        self._index = self._build_index(self.drugs)
        self._loaded = True

    @staticmethod
    def _build_index(drugs: Sequence[Drug]) -> _DrugIndex:
        index = _DrugIndex()
        for drug in drugs:
            index.folded_names.append(confusion_fold(drug.drug_name))
            index.name_numbers.append(bare_name_numbers(drug.drug_name))
            index.strength_keys.append(
                strength_keys(f"{drug.drug_name} {drug.strength}")
            )

            folded: list[str] = []
            for ingredient in drug.ingredients():
                key = matching_key(ingredient)
                if len(key) < 4:  # too short to match reliably inside free text
                    continue
                folded.append(key)
                index.ingredient_vocab.setdefault(key, ingredient)
            index.folded_ingredients.append(folded)
        return index

    # -- public API --------------------------------------------------------

    def resolve(
        self,
        lines: Iterable[str],
        limit: int | None = None,
    ) -> dict[str, object]:
        """Rank drugs against OCR lines.

        Returns ``{candidates, strengths, possible_ingredients, status}``.
        """
        if not self.loaded:
            self.load()

        limit = limit or self.settings.max_candidates
        ocr_lines = [line.strip() for line in lines if line and line.strip()]
        if not ocr_lines:
            return {
                "candidates": [],
                "strengths": [],
                "possible_ingredients": [],
                "status": "uncertain",
            }

        # Space-joined rather than newline-joined so a strength broken across
        # two OCR regions ("650" / "mg") is still read as one value.
        page_text = " ".join(ocr_lines)
        detected_strengths = extract_strengths(page_text)
        detected_strength_keys = strength_keys(page_text)
        possible_ingredients = self._detect_ingredients(page_text)

        phrases = line_windows(ocr_lines, self.settings.max_line_window)
        # Prescription rows commonly print ``brand (ingredient)``. Score the
        # visible brand portion separately as well as the complete auditable
        # line; otherwise a long ingredient name dilutes a one-glyph brand OCR
        # error and generic products crowd out the actual brand (don7:
        # ``Spetcely 200mg (Cetpodoxime)`` -> ``Spetcefy-200``).
        brand_heads = [
            phrase.split("(", 1)[0].strip()
            for phrase in phrases
            if "(" in phrase and len(phrase.split("(", 1)[0].strip()) >= 4
        ]
        # A one-glyph omission in a short brand gets diluted by strength/pack
        # text (don16: ``Aussin SR 60ml`` versus ``Atussin``) and can miss the
        # shortlist entirely. Individual alphabetic brand-head tokens are
        # recall-only phrases; the normal full scoring and threshold still
        # decide whether they may be shown.
        brand_tokens = [
            token
            for head in brand_heads
            for token in re.findall(r"[A-Za-zÀ-ỹ]{5,}", head)
        ]
        phrases = unique([*phrases, *brand_heads, *brand_tokens])

        # Cheap recall pass over the whole database, then an exact rerank of
        # only the survivors.
        folded_phrases, coarse = self._coarse_name_scores(phrases)
        shortlist = self._shortlist(coarse, possible_ingredients)
        name_scores = self._refine_name_scores(folded_phrases, shortlist)

        scored: list[tuple[float, dict[str, float], int, int, int]] = []
        for i in shortlist:
            parts = {
                "name_score": name_scores[i],
                "strength_score": self._strength_score(i, detected_strength_keys),
                "ingredient_score": self._ingredient_score(i, possible_ingredients),
            }
            final = (
                parts["name_score"] * self.settings.weight_name
                + parts["strength_score"] * self.settings.weight_strength
                + parts["ingredient_score"] * self.settings.weight_ingredient
            )
            # An exact brand token is stronger evidence than a fuzzy match on
            # a related generic product. Keep a small deterministic bonus so
            # ``Advagraf`` wins over another tacrolimus brand when the OCR
            # line explicitly contains that brand.
            folded_name = self._index.folded_names[i]
            positions = [
                position
                for phrase in folded_phrases
                if len(folded_name) >= 4
                for position in [self._name_position(phrase, folded_name)]
                if position is not None
            ]
            if positions:
                final = min(1.0, final + 0.02)
            # Where the name matched, not just whether. A prescription row
            # reads "YESOM 40 40mg (Esomeprazol 40mg)": the brand is at the
            # front, the active ingredient sits inside the parentheses behind
            # it. Both are exact matches scoring name=1.00, so without this the
            # tie is settled by CSV row order and the generic wins half the
            # time -- the database holds "Yesom 40" and returns "Esomeprazol
            # 40". Measured over six real prescription rows: 3/6 correct
            # before, 6/6 after.
            earliest = min(positions) if positions else _NO_NAME_MATCH
            exact_name_length = len(folded_name) if positions else 0
            scored.append((final, parts, i, earliest, exact_name_length))

        # Tie-break on name score so a strength/ingredient bonus never lets a
        # clearly worse-spelled brand overtake an exact name match, then on
        # how early the name appeared in the OCR line.
        scored.sort(
            key=lambda item: (
                item[0], item[1]["name_score"], -item[3], item[4]
            ),
            reverse=True,
        )
        top = scored[:limit]

        candidates = [
            self._as_candidate(self.drugs[i], final, parts)
            for final, parts, i, _earliest, _exact_name_length in top
        ]
        # Thà không đề xuất gì còn hơn đề xuất bừa: một dòng OCR hỏng luôn tìm được
        # thuốc "gần giống" trong danh mục 43.970 tên, và người dùng khó biết đó là
        # rác. Không còn ứng viên nào thì giao diện chuyển dòng đó sang nhập tay.
        floor = self.settings.min_candidate_score
        if floor > 0:
            candidates = [c for c in candidates if c["score"] >= floor]
        return {
            "candidates": candidates,
            "strengths": detected_strengths,
            "possible_ingredients": possible_ingredients,
            "status": self.status_for(candidates[0]["score"] if candidates else 0.0),
        }

    def status_for(self, score: float) -> str:
        if score >= self.settings.drug_high_confidence:
            return "high_confidence"
        if score >= self.settings.drug_medium_confidence:
            return "medium_confidence"
        return "uncertain"

    # -- scoring signals ---------------------------------------------------

    @staticmethod
    def _name_position(phrase: str, drug_name: str) -> int | None:
        """Whole-token containment position, never a substring inside a word."""
        start = phrase.find(drug_name)
        while start >= 0:
            end = start + len(drug_name)
            left_ok = start == 0 or phrase[start - 1] not in "abcdefghijklmnopqrstuvwxyz0123456789"
            right_ok = end == len(phrase) or phrase[end] not in "abcdefghijklmnopqrstuvwxyz0123456789"
            if left_ok and right_ok:
                return start
            start = phrase.find(drug_name, start + 1)
        return None

    def _coarse_name_scores(self, phrases: list[str]) -> tuple[list[str], np.ndarray]:
        """Recall pass over the whole database: cheap scorers only.

        ``WRatio`` would be the natural choice but it costs ~160 ms against
        44k rows, blowing the whole resolver budget on its own. ``ratio``
        (~4 ms) and ``token_set_ratio`` (~30 ms) together recover the same
        rows: the first catches near-exact names, the second catches names
        surrounded by extra pack text. Precision is not needed yet -- this pass
        only has to get the right row *into* the shortlist, where the expensive
        scorer reranks it.

        ``cdist`` scores the whole phrase x drug matrix in native code across
        all cores.
        """
        folded_phrases = unique(confusion_fold(p) for p in phrases)
        kwargs = {"workers": -1, "dtype": np.float32}
        exact = process.cdist(folded_phrases, self._index.folded_names, scorer=fuzz.ratio, **kwargs)
        tokens = process.cdist(
            folded_phrases, self._index.folded_names, scorer=fuzz.token_set_ratio, **kwargs
        )
        scores = np.maximum(exact, tokens).max(axis=0)
        # A prescription line often contains generic name, brand, strength and
        # pack information together. If the exact database brand is present as
        # a token inside that longer OCR phrase, preserve it in recall even
        # when the whole-line fuzzy score is diluted by the extra text.
        for phrase in folded_phrases:
            for index, drug_name in enumerate(self._index.folded_names):
                if len(drug_name) >= 4 and self._name_position(phrase, drug_name) is not None:
                    scores[index] = max(scores[index], 100.0)
        return folded_phrases, scores

    def _refine_name_scores(
        self,
        folded_phrases: list[str],
        shortlist: list[int],
    ) -> dict[int, float]:
        """Rerank pass: average ``WRatio`` with the length-sensitive ``ratio``.

        ``WRatio`` alone awards a flat 95 to *every* substring containment, so
        "Augmentin 625" and "Augmentin 1g" tie against a phrase reading
        "AUGMENTlN". ``ratio`` is length-sensitive and breaks exactly those
        ties, but on its own it punishes the extra pack text OCR always picks
        up -- hence the blend. The recall pass's scores are discarded here: they
        only decided *which* rows get this treatment. Running both scorers over
        the shortlist alone keeps the cost independent of database size.
        """
        subset = [self._index.folded_names[i] for i in shortlist]
        kwargs = {"workers": -1, "dtype": np.float32}
        weighted = process.cdist(folded_phrases, subset, scorer=fuzz.WRatio, **kwargs).max(axis=0)
        plain = process.cdist(folded_phrases, subset, scorer=fuzz.ratio, **kwargs).max(axis=0)
        scores = {
            index: float((weighted[position] + plain[position]) / 200.0)
            for position, index in enumerate(shortlist)
        }
        # Preserve an exact brand hit inside a noisy, longer OCR line. This
        # is especially important for prescription rows such as
        # ``Tacrolimus ... (Advagraf 0.5mg)`` where the resolver receives the
        # complete name-column evidence as one OCR box.
        for position, index in enumerate(shortlist):
            drug_name = self._index.folded_names[index]
            if len(drug_name) >= 4 and any(
                self._name_position(phrase, drug_name) is not None
                for phrase in folded_phrases
            ):
                scores[index] = max(scores[index], 1.0)
        return scores

    def _shortlist(self, coarse_scores: np.ndarray, ingredients: list[str]) -> list[int]:
        """Rows worth a full rescore: best names, plus exact ingredient hits."""
        size = min(self.settings.shortlist_size, len(coarse_scores))
        top = np.argpartition(coarse_scores, -size)[-size:] if size else np.array([], dtype=int)
        selected = set(int(i) for i in top)

        if ingredients:
            wanted = {matching_key(x) for x in ingredients}
            # An unreadable brand name can still be pinned down by ingredient.
            for i, folded in enumerate(self._index.folded_ingredients):
                if folded and wanted.issuperset(folded):
                    selected.add(i)
                    if len(selected) > size * 4:
                        break
        return sorted(selected)

    def _strength_score(self, index: int, detected: set[str]) -> float:
        """Fraction of the doses printed on the pack that this product has.

        Numbers are read from both the ``strength`` column and the drug name,
        because Vietnamese brand names encode the dose ("Augmentin 625") more
        often than the CSV spells it out.

        Scored as recall over the *detected* doses, not as symmetric overlap:
        a row is not at fault for listing strengths the photo happens not to
        show. Grading it (rather than a boolean "any match") is what separates
        combination products that share a component -- a pack reading 875 mg +
        125 mg confirms both of "Augmentin 1g" (875+125 -> 1.0) but only half
        of "Augmentin 625" (500+125 -> 0.5).
        """
        if not detected:
            return self.settings.strength_neutral_score()
        known = self._index.strength_keys[index]
        aliases = self._index.name_numbers[index]
        if not known and not aliases:
            # Missing data in the database is not evidence against the row.
            return self.settings.strength_neutral_score()
        matched = 0
        for key in detected:
            # Unit-aware evidence is authoritative. Only a genuinely unit-less
            # number in the product name may act as a fallback dose alias.
            amount = key.partition(":")[2]
            if key in known or amount in aliases:
                matched += 1
        return matched / len(detected)

    def _ingredient_score(self, index: int, detected: list[str]) -> float:
        """Fraction of this drug's ingredients that the image confirms."""
        folded = self._index.folded_ingredients[index]
        if not folded or not detected:
            return 0.0
        wanted = {matching_key(x) for x in detected}
        return sum(1 for ing in folded if ing in wanted) / len(folded)

    def _detect_ingredients(self, text: str) -> list[str]:
        """Ingredient names present in text, with a guarded OCR-error fallback."""
        key = matching_key(text)
        if not key:
            return []
        found = [
            display
            for folded, display in self._index.ingredient_vocab.items()
            if folded in key
        ]
        # A single damaged glyph in a long ingredient should not discard strong
        # evidence (don7: ``Cetpodoxime`` instead of ``Cefpodoxime``). Only use
        # one high-scoring, >=8-character fuzzy match when no literal ingredient
        # was found. Short names are intentionally excluded because a 90%
        # partial match inside free text is not distinctive enough for them.
        if not found:
            long_ingredients = [
                folded for folded in self._index.ingredient_vocab if len(folded) >= 8
            ]
            fuzzy = process.extract(
                key,
                long_ingredients,
                scorer=fuzz.partial_ratio,
                score_cutoff=90.0,
                limit=1,
            )
            if fuzzy:
                found.append(self._index.ingredient_vocab[fuzzy[0][0]])
        # Drop components subsumed by a longer match (e.g. "Amoxicillin" inside
        # "Amoxicillin trihydrate") to keep the reported list readable.
        found.sort(key=len, reverse=True)
        kept: list[str] = []
        for item in found:
            item_key = matching_key(item)
            if not any(item_key in matching_key(other) for other in kept):
                kept.append(item)
        return unique(kept)

    # -- output ------------------------------------------------------------

    @staticmethod
    def _as_candidate(drug: Drug, score: float, parts: dict[str, float]) -> dict[str, object]:
        return {
            "drug_id": drug.id,
            "drug_name": drug.drug_name,
            "active_ingredient": drug.active_ingredient,
            "strength": drug.strength,
            "dosage_form": drug.dosage_form,
            "manufacturer": drug.manufacturer,
            "registration_number": drug.registration_number,
            "score": round(float(score), 4),
            "score_breakdown": {k: round(float(v), 4) for k, v in parts.items()},
        }
