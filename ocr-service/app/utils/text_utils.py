"""Text normalization and strength extraction.

Two rules drive this module:

1. The raw OCR string is never mutated. Normalization produces *separate*
   comparison keys; ``raw_text`` always survives to the API response.
2. OCR confusion repair (``0``/``O``, ``1``/``I``/``l``, ``5``/``S``, ``8``/``B``)
   is applied as a *fold* to both sides of a comparison rather than as a guess
   about which character was intended. Folding "HAPAC0L 65O" and "Hapacol 650"
   both to "hapacoi 6so" makes them compare equal without either string being
   rewritten.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Iterable

# Each group collapses to a single representative during folding.
OCR_CONFUSION_GROUPS: tuple[tuple[str, ...], ...] = (
    ("0", "o"),
    ("1", "i", "l"),
    ("5", "s"),
    ("8", "b"),
)

# Built from the groups above: every member maps to the group's first member.
_FOLD_MAP: dict[str, str] = {
    member: group[0] for group in OCR_CONFUSION_GROUPS for member in group
}

_DASHES = re.compile(r"[‐-―−]")
_QUOTES = re.compile(r"[‘’‛′]")
_DQUOTES = re.compile(r"[“”‟″]")
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")

_UNIT = r"(?:mg|mcg|µg|ug|g|kg|ml|l|iu|ui|%)"
_NUMBER = r"\d+(?:[.,]\d+)?"
# Two guards matter as much as the pattern itself:
#   * the leading look-behind stops a match starting mid-token, which is what
#     made OCR's "HAPAC0L" register as "0 L" (zero litres);
#   * the trailing look-ahead stops a unit matching the start of a longer word
#     ("10 vien" must not read as 10 litres).
# The per-something tail is one optional group with an optional number, so that
# both "125 mg/5 ml" and "10 mg/ml" are captured whole rather than truncated to
# the leading "125 mg" / "10 mg".
_STRENGTH_PATTERN = re.compile(
    rf"""
    (?<![A-Za-z0-9.,])                           # not inside a word or number
    {_NUMBER}\s*{_UNIT}                          # 500 mg, 650mg, 0.5%, 1000 IU
    (?:\s*/\s*(?:{_NUMBER}\s*)?{_UNIT})?         # /5 ml, /ml, / 125 mg
    (?![A-Za-z0-9])                              # unit is a whole token
    """,
    re.IGNORECASE | re.VERBOSE,
)

_UNIT_CANONICAL = {
    "mg": "mg",
    "mcg": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "g": "g",
    "kg": "kg",
    "ml": "ml",
    "l": "l",
    "iu": "IU",
    "ui": "IU",
    "%": "%",
}

_NUMBER_RE = re.compile(_NUMBER)
_STRENGTH_PIECE = re.compile(rf"({_NUMBER})\s*({_UNIT})", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Human-readable cleanup: unicode, punctuation, whitespace, line breaks.

    Case is preserved -- lowercasing belongs to :func:`matching_key`, because
    the normalized text is shown to users.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _DASHES.sub("-", text)
    text = _QUOTES.sub("'", text)
    text = _DQUOTES.sub('"', text)
    text = _HORIZONTAL_SPACE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def strip_diacritics(text: str) -> str:
    """Fold Vietnamese tone marks away. Comparison-only, never displayed.

    OCR reads Vietnamese packaging inconsistently: "Hạ sốt" comes back as
    "Ha söt", "huyết" as "huyét". Those cost 5-23 points of similarity against
    a database full of correctly-accented names, purely from tone marks that
    carry no information for drug identification. Folding both sides to ASCII
    makes the comparison ignore them.
    """
    # d-stroke has no combining form, so NFD alone would leave it untouched.
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if not unicodedata.combining(char)
    )


def matching_key(text: str) -> str:
    """Case-folded, accent-folded, single-spaced key used for fuzzy comparison."""
    return strip_diacritics(normalize_text(text).replace("\n", " ").casefold()).strip()


def confusion_fold(text: str) -> str:
    """Collapse OCR-confusable characters so both sides of a match agree.

    Comparison-only. Never write the result back into ``raw_text``.
    """
    return "".join(_FOLD_MAP.get(char, char) for char in matching_key(text))


def _canonical_strength(fragment: str) -> str:
    """Render one matched fragment as e.g. ``650 mg`` / ``125 mg/5 ml``."""
    fragment = fragment.replace(",", ".")

    def render(match: re.Match[str]) -> str:
        number, unit = match.group(1), match.group(2).lower()
        number = number.rstrip("0").rstrip(".") if "." in number else number
        canonical = _UNIT_CANONICAL.get(unit, unit)
        separator = "" if canonical == "%" else " "
        return f"{number}{separator}{canonical}"

    rendered = _STRENGTH_PIECE.sub(render, fragment)
    rendered = re.sub(r"\s*/\s*", "/", rendered)
    return re.sub(r"\s+", " ", rendered).strip()


def extract_strengths(text: str) -> list[str]:
    """Pull dosage strengths out of free text.

    >>> extract_strengths("Augmentin 625: 500 mg / 125 mg")
    ['500 mg/125 mg']
    >>> extract_strengths("650mg")
    ['650 mg']
    """
    found = (_canonical_strength(m.group(0)) for m in _STRENGTH_PATTERN.finditer(text or ""))
    return unique(x for x in found if x)


def strength_numbers(text: str) -> set[str]:
    """Numeric part of every strength in ``text``, normalized for comparison.

    Used to tell "Augmentin 625" from "Augmentin 1g" when the CSV strength
    column and the printed pack text disagree on formatting.
    """
    numbers: set[str] = set()
    for raw in _NUMBER_RE.findall((text or "").replace(",", ".")):
        value = float(raw)
        numbers.add(str(int(value)) if value.is_integer() else str(value))
    return numbers


def bare_name_numbers(text: str) -> set[str]:
    """Numbers that are not already part of an explicit strength.

    Vietnamese product names often encode a dose without a unit (``Augmentin
    625``), so those numbers remain useful aliases. A number that *does* carry a
    unit must not be treated this way: otherwise ``Drug 1 mg`` and ``Drug 1 g``
    both collapse to the alias ``1`` and receive the same strength score.
    """
    without_strengths = _STRENGTH_PATTERN.sub(" ", text or "")
    return strength_numbers(without_strengths)


def _decimal_text(value: Decimal) -> str:
    """Stable, non-scientific rendering used inside comparison-only keys."""
    rendered = format(value.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def strength_keys(text: str) -> set[str]:
    """Unit-aware strength components normalized for comparison.

    Masses become milligrams and volumes become millilitres, so ``1 g`` matches
    ``1000 mg`` while ``1 g`` never matches ``1 mg``. Ratio strengths retain
    both dimensions: ``500 mg/5 ml`` becomes ``mass:500`` + ``volume:5`` and
    therefore cannot fully match ``500 mg + 5 mg``.
    """
    keys: set[str] = set()
    for strength in _STRENGTH_PATTERN.finditer(text or ""):
        for piece in _STRENGTH_PIECE.finditer(strength.group(0).replace(",", ".")):
            raw_number, raw_unit = piece.group(1), piece.group(2).lower()
            try:
                value = Decimal(raw_number.replace(",", "."))
            except InvalidOperation:
                continue

            unit = _UNIT_CANONICAL.get(raw_unit, raw_unit)
            if unit == "kg":
                dimension, value = "mass", value * Decimal("1000000")
            elif unit == "g":
                dimension, value = "mass", value * Decimal("1000")
            elif unit == "mg":
                dimension = "mass"
            elif unit == "mcg":
                dimension, value = "mass", value / Decimal("1000")
            elif unit == "l":
                dimension, value = "volume", value * Decimal("1000")
            elif unit == "ml":
                dimension = "volume"
            elif unit == "IU":
                dimension = "iu"
            elif unit == "%":
                dimension = "percent"
            else:
                dimension = unit.casefold()
            keys.add(f"{dimension}:{_decimal_text(value)}")
    return keys


def unique(values: Iterable[str]) -> list[str]:
    """De-duplicate case-insensitively while preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = matching_key(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def line_windows(lines: list[str], max_window: int) -> list[str]:
    """Every run of 1..max_window consecutive lines, joined by a space.

    ``["HAPAC0L", "65O"]`` yields ``["HAPAC0L", "65O", "HAPAC0L 65O"]`` so a
    brand name split across two printed lines can still match one DB row.
    """
    cleaned = [line.strip() for line in lines if line and line.strip()]
    windows: list[str] = []
    for size in range(1, max(1, max_window) + 1):
        for start in range(len(cleaned) - size + 1):
            windows.append(" ".join(cleaned[start : start + size]))
    return unique(windows)
