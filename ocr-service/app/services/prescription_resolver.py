"""Document classification and row extraction for prescription images."""

from __future__ import annotations

import re
from statistics import median
from typing import Any

from rapidfuzz import fuzz

from app.utils.text_utils import matching_key

_PRESCRIPTION_MARKERS = (
    # Include frequent OCR variants: ``DON THUC`` / ``DON THU`` when the
    # Vietnamese ``Ố``/``UỐC`` is lost by the recognizer.
    "don thuoc", "don thuc", "don thu", "donthuoc", "donthuc",
    "thong tin benh nhan", "thong tin don thuoc", "cach dung",
    "toa thuoc", "toa thuoc mua", "thuoc mua", "benh vien", "ma benh nhan",
    "kho xuat", "chan doan", "bac si",
)
# Characters OCR produces for the "." after a row number. The comma is not
# hypothetical: on a real Bình Dân prescription, ``4.`` came back as ``4,``,
# which silently disqualified the row. ``:`` and ``;`` fail the same way.
# Deliberately excludes ``:`` -- that would make the header time ``12:46`` parse
# as row 12, which the pattern below is specifically written to avoid.
_ROW_SEPARATOR = r"[.,/)\-]"
# A stray pen stroke in the row-number column gets detected as its own glyph and
# glued to the front of the row, e.g. ``(2. SUCRATE GEL``. Allow a little
# leading punctuation so handwriting in the margin cannot hide a medication.
# Letters and digits are excluded, so a real medicine name cannot match here.
_LEADING_INK = r"[^\w\s]{0,2}\s*"
# Do not accept the time in a prescription header (e.g. ``12:46``) as a
# medication row: a row number must be followed by a separator or whitespace.
# The surrounding geometry gates in extract_medication_rows are what keep this
# permissive pattern from turning dates and quantities into rows.
_ROW_NUMBER = re.compile(rf"^\s*{_LEADING_INK}(\d{{1,2}})(?:{_ROW_SEPARATOR}|\s|$)")
_PACKAGE_STOPWORDS = (
    "health supplement", "gmp", "box of", "tablet", "tablets", "blister",
    "formulation", "paracetamol", "caffeine", "giam", "dau", "tac dung",
    "khong", "gay buon", "vien nen", "film-coated",
)
_TABLE_FOOTER_MARKERS = (
    "cong khoan", "tong khoan", "tong 7 khoan", "loi dan", "benh nhan", "nguoi giao", "bac si dieu tri",
    "bac si ke don", "phong tai kham", "ck noi tiet", "ck nqi tiet", "thuoc chong thai",
    "lien he", "tiep tuc duy tri", "thuoc dtd", "hen kham lai", "toa cap ngay", "ngay ke don", "tai kham",
    "bac si", "dan cun", "shichu", "ck ni tiet", "ck ni tit",
    "stt", "ten thuoc", "don vi sl",
)
_SCHEDULE_MARKERS = (
    "ngay uong", "moi lan", "kho cap phat", "bhyt ngoai tru",
    "sang", "sing", "slng", "trua", "trura", "tra", "chieu", "ghi chu", "shichu", "ang", "ng",
)


# Footer wording is matched fuzzily, not by substring. Two single-character OCR
# errors on a real prescription -- "bác sĩ" read as "bás sĩ" and "Ghi chú" as
# "chi chú" -- were enough to slip the whole signature block past an exact
# check, which then surfaced as a seventh medication that does not exist.
# Measured on that page: real footer wording scores 83-100 against these
# markers, real medicine names 40-60, so the cutoff sits in a 23-point gap.
_FOOTER_FUZZ_CUTOFF = 75
# Short markers are kept on exact matching; at three or four characters a fuzzy
# score says nothing useful and would start swallowing drug names.
_FUZZY_FOOTER_MARKERS = tuple(m for m in _TABLE_FOOTER_MARKERS if len(m) >= 6)
_EXACT_FOOTER_MARKERS = tuple(m for m in _TABLE_FOOTER_MARKERS if len(m) < 6)


def is_table_footer(text: str) -> bool:
    """True for the signature/total block printed below the medication table."""
    key = matching_key(text)
    if not key:
        return False
    if any(marker in key for marker in _EXACT_FOOTER_MARKERS):
        return True
    return any(
        fuzz.partial_ratio(marker, key) >= _FOOTER_FUZZ_CUTOFF
        for marker in _FUZZY_FOOTER_MARKERS
    )


def _is_schedule_text(text: str) -> bool:
    """Recognize dosage instructions, including common OCR errors like ``Ivx``."""
    key = matching_key(text).strip()
    if key.startswith(_SCHEDULE_MARKERS):
        return True
    # Topical instructions are frequently printed on the line below the
    # product name, e.g. ``xoa lung dau``. VietOCR may read ``lung`` as
    # ``hung``; the line is still an instruction, never another medicine.
    if key.startswith(("xoa ", "boi ", "bôi ")):
        return True
    # On low-quality prescriptions PaddleOCR often reads "1vx/2vx" for
    # "1 lần/2 lần". These are instructions, never medicine names.
    return bool(re.match(r"^[ilvtd\d]{1,3}\s*[vxyr]\s*x?\s*\d+\s*(?:lần|lan)\b", key)) or bool(
        re.match(r"^\S{0,5}x\s*\d+\s*(?:lần|lan)\b", key)
    )


def _row_number(text: str, x1: float, page_right: float) -> int | None:
    """Read a prescription row number, including Paddle's ``I`` for ``1``.

    The first row in low-resolution phone screenshots is frequently returned
    as a standalone capital ``I``.  It is only accepted at the extreme left
    of the page, so normal words such as ``I.THÔNG TIN...`` cannot become a
    medicine row.
    """
    match = _ROW_NUMBER.match(text)
    if match:
        number = int(match.group(1))
        if number <= 99:
            return number
    if x1 <= page_right * 0.12 and text.strip().casefold() in {"i", "l", "|"}:
        return 1
    return None


def _clean_medication_name(text: str) -> str:
    """Remove a dosage tail when OCR puts name and instructions in one box."""
    # In blurry prescriptions PaddleOCR commonly joins the medicine name and
    # dosage instruction, e.g. ``Dai tan giao 3vx3 lan/ngay`` or
    # ``Ginkobil Ivx3 lan/ngay``.  ``3vx``/``Ivx`` are OCR variants of
    # ``3 lần``/``1 lần`` and must never be sent to the drug matcher.
    cleaned = re.split(
        r"\b(?:ngày|ngay|sáng|sang|sing|chiều|chieu|tối|toi|trưa|trua|trura|"
        r"tra|ghi\s+chú|ghi\s+chu|shichu)\b|"
        r"\b[ilvtd\d]{1,3}\s*[vxyr]\s*x?\s*\d+\s*(?:lần|lan)\b|"
        r"\b\d{1,4}\s*(?:lần|lan)\b|\b\S{0,5}x\s*\d+\s*(?:lần|lan)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    # When the name and dosage are detected in one box, cut at the dosage
    # prefix even if OCR mangles ``lần/ngày`` afterwards (e.g. ``Iv x 2 lán/ ngy``).
    cleaned = re.split(
        r"\b[ilvtd\d]{1,3}\s*[vxyr]\s*x?\s*\d+\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    # A footer can be glued to the final medicine row by OCR. It must not be
    # treated as part of the medicine name or sent to the drug matcher.
    footer_key = matching_key(cleaned)
    for marker in _TABLE_FOOTER_MARKERS:
        marker_pos = footer_key.find(marker)
        if marker_pos >= 0:
            # Use the same character offset because matching_key preserves
            # whitespace/order even though it removes accents.
            cleaned = cleaned[:marker_pos]
            break
    # Remove pack/quantity annotations such as ``(H/100v)``, ``(Ch/40v)``.
    # Keep strengths such as ``4mg`` and ``0.5mg``: they are part of the OCR
    # medicine identity and are essential evidence for database matching.
    cleaned = re.sub(
        r"\(\s*(?:h\s*v?|ch|lo|lọ)\s*/\s*\d{1,4}\s*[a-z%]*\s*\)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # OCR sometimes loses an opening parenthesis in a brand/alias segment;
    # preserve balanced aliases such as ``(Shunorac)``.
    if cleaned.count(")") > cleaned.count("("):
        cleaned = re.sub(r"\s*[)]", " ", cleaned, count=cleaned.count(")") - cleaned.count("("))
    # Strip the row number itself. Must accept exactly the separators
    # _ROW_NUMBER accepts, or a row matched as ``4,`` keeps ``4,`` in its name
    # and is sent to the drug matcher that way.
    cleaned = re.sub(rf"^\s*{_LEADING_INK}\d{{1,2}}\s*{_ROW_SEPARATOR}\s*", "", cleaned)
    return cleaned.strip(" -:(,")


def classify_document(items: list[dict[str, Any]]) -> str:
    """Classify from OCR text; a medicine box has no patient/prescription table."""
    text = matching_key(" ".join(item["text"] for item in items))
    marker_count = sum(marker in text for marker in _PRESCRIPTION_MARKERS)
    if marker_count >= 2 or any(marker in text for marker in ("don thuoc", "don thuc", "don thu", "donthuoc", "donthuc")):
        return "prescription"
    if items:
        return "medicine_package"
    return "unknown"


def extract_package_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select prominent brand-name OCR regions from a medicine package.

    This is intentionally conservative: it keeps short, prominent label text
    and excludes marketing/copy text. The returned OCR text is shown to the
    user before any database candidate is proposed.
    """
    candidates = []
    for item in items:
        text = " ".join(item.get("text", "").split()).strip()
        key = matching_key(text)
        if not text or len(text) > 32 or any(stop in key for stop in _PACKAGE_STOPWORDS):
            continue
        if re.fullmatch(r"\d+|B", text, flags=re.IGNORECASE):
            continue
        if not re.search(r"[A-Za-zÀ-ỹ]", text):
            continue
        points = item.get("bbox") or []
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            area = max(1.0, max(xs) - min(xs)) * max(1.0, max(ys) - min(ys))
            y = min(ys)
        else:
            area, y = 0.0, len(candidates)
        candidates.append({**item, "text": text, "_area": area, "_y": y})

    # Large label lettering is a stronger brand signal than small packaging
    # copy. Keep at most three regions and restore their reading order.
    selected = sorted(candidates, key=lambda item: item["_area"], reverse=True)[:3]
    return sorted(selected, key=lambda item: (item["_y"], item.get("bbox", [[0, 0]])[0][0]))


def extract_medication_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group OCR boxes into numbered prescription rows.

    OCR geometry is used only for layout. The actual medicine identity is still
    resolved by DrugResolver, and each row remains a candidate requiring user
    confirmation.
    """
    with_boxes = [item for item in items if item.get("bbox")]
    if not with_boxes:
        # Useful fallback for OCR engines/tests that do not expose geometry.
        rows: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for item in items:
            text = item["text"].strip()
            match = _ROW_NUMBER.match(text)
            if match:
                if current:
                    rows.append(current)
                current = {"row_number": int(match.group(1)), "items": [item], "texts": [text]}
            elif current:
                current["items"].append(item)
                current["texts"].append(text)
        if current:
            rows.append(current)
        for row in rows:
            name_texts = [_clean_medication_name(text) for text in row["texts"]]
            name_texts = [text for text in name_texts if text and re.search(r"[A-Za-zÀ-ỹ]", text)]
            row["name_texts"] = name_texts
            row["resolver_texts"] = name_texts[:]
            row["name_items"] = row["items"]
        return rows

    def rect(item: dict[str, Any]) -> tuple[float, float, float, float]:
        points = item["bbox"]
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        return min(xs), min(ys), max(xs), max(ys)

    ordered = sorted(with_boxes, key=lambda item: (rect(item)[1], rect(item)[0]))
    page_right = max(rect(item)[2] for item in ordered)
    # Restrict row-number detection to the medication section. This prevents
    # phone screenshot artefacts (20:32, battery 86), age, and house numbers
    # from becoming fake medication rows.
    section_start_y = 0.0
    section_end_y = float("inf")
    for item in ordered:
        key = matching_key(item["text"])
        if (
            "thong tin don thuoc" in key
            or any(marker in key for marker in ("don thuoc", "don thuc", "don thu", "donthuoc", "donthuc"))
            or "toa thuoc" in key
            or key.startswith(("dieu tri", "dieu ti"))
        ):
            # Ignore later footer instructions containing words such as
            # ``đơn thuốc``; the medication table is near the upper part of
            # the page and must remain the active section boundary.
            if rect(item)[1] < 800:
                section_start_y = max(section_start_y, rect(item)[3])
        # Some Bạch Mai templates lose the Roman numeral/header but retain
        # the table headings.  Starting after these headings prevents patient
        # age, codes and barcode digits from becoming medicine rows.
        if key.startswith("stt") or "ten thuoc" in key or "ten thuc" in key:
            section_start_y = max(section_start_y, rect(item)[3])
        if section_start_y and rect(item)[1] > section_start_y + 100 and any(
            marker in key for marker in (
                "loi dan", "ngay tai kham", "toa cap ngay", "bac si kham", "bac si dieu tri", "bac si"
            )
        ):
            section_end_y = min(section_end_y, rect(item)[1])
    # Locate row numbers by geometry. Clustering all text by line height can
    # merge wrapped lines from adjacent rows, especially in phone screenshots.
    row_markers = []
    for item in ordered:
        x1, y1, x2, y2 = rect(item)
        text = item["text"].strip()
        number = _row_number(text, x1, page_right)
        marker_y = (y1 + y2) / 2
        # Dosage instructions are often OCR'd as ``3vx ...`` or ``1vx ...``.
        # They begin with a number too, but are never medication rows.
        if (
            number is not None
            and not _is_schedule_text(text)
            and section_start_y < marker_y < section_end_y
            and x1 <= page_right * 0.35
        ):
            # A bare number is accepted only near the left edge (row-number
            # column); a number followed by '.' can be part of the OCR text
            # in the medicine-name column, e.g. ``1.YESOM 40``.
            has_separator = bool(
                re.match(rf"^\s*{_LEADING_INK}\d{{1,2}}(?:{_ROW_SEPARATOR}|\s)", text)
            ) or text.strip().casefold() in {"i", "l", "|"}
            if has_separator or x1 <= page_right * 0.12:
                row_markers.append((number, (y1 + y2) / 2))

    if not row_markers:
        row_markers = []
        for item in ordered:
            text = item["text"].strip()
            marker_y = (rect(item)[1] + rect(item)[3]) / 2
            number = _row_number(text, rect(item)[0], page_right)
            if number is not None and not _is_schedule_text(text) and section_start_y < marker_y < section_end_y:
                row_markers.append((number, marker_y))

    # The prescription table's name column ends before the unit/quantity
    # columns. Estimate that boundary from the page width; this prevents
    # dosage and warehouse instructions becoming part of the drug name.
    name_column_right = page_right * 0.48
    rows: list[dict[str, Any]] = []
    for marker_index, (row_number, marker_y) in enumerate(row_markers):
        next_marker_y = row_markers[marker_index + 1][1] if marker_index + 1 < len(row_markers) else float("inf")
        # The last row has no following number; cap its wrapped text window so
        # the table footer and signature area are not attached to that drug.
        next_y = marker_y + 160 if next_marker_y == float("inf") else (marker_y + next_marker_y) / 2
        row_items = [
            item for item in ordered
            if marker_y - 12 <= (rect(item)[1] + rect(item)[3]) / 2 < next_y
            and not is_table_footer(item["text"])
        ]
        rows.append({"row_number": row_number, "items": row_items})

    # Some OCR results lose the first row number but keep the standalone slash
    # next to it. Recover a name block before the first detected row marker.
    if row_markers and row_markers[0][0] > 1:
        first_number, first_y = row_markers[0]
        first_items = [
            item for item in ordered
            if first_y - 75 < (rect(item)[1] + rect(item)[3]) / 2 < first_y - 15
            and rect(item)[0] <= name_column_right
            and not _is_schedule_text(item["text"])
            and not is_table_footer(item["text"])
        ]
        if first_items:
            rows.insert(0, {"row_number": first_number - 1, "items": first_items})

    # A second table on the same prescription often restarts numbering at 1.
    # Expose one continuous medication list to the resolver/UI.
    previous_number = 0
    for row in rows:
        if row["row_number"] <= previous_number:
            row["row_number"] = previous_number + 1
        previous_number = row["row_number"]

    # OCR can miss the number in the first column of a wrapped final row.
    # When the name column shows a large vertical gap, recover that row split
    # without guessing a medicine name.
    if rows:
        last = rows[-1]
        name_items = [
            item for item in last["items"]
            if rect(item)[0] <= name_column_right
            and not _ROW_NUMBER.fullmatch(item["text"].strip())
            and item["text"].strip().casefold() not in {"i", "l", "|"}
            and not _is_schedule_text(item["text"])
        ]
        name_items.sort(key=lambda item: (rect(item)[1], rect(item)[0]))
        for previous, current in zip(name_items, name_items[1:]):
            previous_y = (rect(previous)[1] + rect(previous)[3]) / 2
            current_y = (rect(current)[1] + rect(current)[3]) / 2
            if current_y - previous_y > 30 and previous_y > last["items"][0].get("_row_marker_y", -1):
                split_y = (previous_y + current_y) / 2
                first_items = [item for item in last["items"] if (rect(item)[1] + rect(item)[3]) / 2 < split_y]
                second_items = [item for item in last["items"] if (rect(item)[1] + rect(item)[3]) / 2 >= split_y]
                if first_items and second_items:
                    rows[-1:] = [
                        {"row_number": last["row_number"], "items": first_items},
                        {"row_number": last["row_number"] + 1, "items": second_items},
                    ]
                break

    result = []
    for row in rows:
        all_items = sorted(row["items"], key=lambda item: (rect(item)[1], rect(item)[0]))
        name_items = [
            item for item in all_items
            if rect(item)[0] <= name_column_right
            and not _ROW_NUMBER.fullmatch(item["text"].strip())
            and item["text"].strip().casefold() not in {"i", "l", "|"}
            and not _is_schedule_text(item["text"])
        ]
        # If a narrow/cropped image has no recognizable name column, preserve
        # all row text rather than returning an empty medication.
        if not any(item["text"].strip() for item in name_items):
            name_items = all_items
        texts = [item["text"].strip() for item in all_items if item["text"].strip()]
        if texts:
            original_name_texts = [
                item["text"].strip()
                for item in name_items
                if item["text"].strip()
                and not re.fullmatch(r"\d{1,3}", item["text"].strip())
                and re.search(r"[A-Za-zÀ-ỹ]", _clean_medication_name(item["text"]))
            ]
            name_texts = [_clean_medication_name(text) for text in original_name_texts]
            name_texts = [text for text in name_texts if text]
            result.append({
                "row_number": row["row_number"],
                "items": all_items,
                "texts": texts,
                "name_texts": name_texts,
                # Keep the unmodified name-column evidence for matching. The
                # display name remains cleaned, while strengths/brand aliases
                # are not lost before DrugResolver sees them.
                "resolver_texts": original_name_texts,
                "name_items": [
                    item for item in name_items
                    if item["text"].strip() in original_name_texts
                ],
            })
    return result


def extract_prescription_conditions(items: list[dict[str, Any]]) -> dict[str, list[str] | str]:
    """Extract printed diagnoses/underlying conditions without medical guessing.

    This deliberately reads only text next to prescription labels such as
    ``Chẩn đoán`` and ``Bệnh kèm theo``.  It does not infer a disease from a
    medicine name, which keeps the OCR output auditable and safe to confirm.
    """
    lines = [" ".join(str(item.get("text", "")).split()).strip() for item in items]
    lines = [line for line in lines if line]
    diagnosis = ""
    conditions: list[str] = []
    icd_codes: list[str] = []
    for index, line in enumerate(lines):
        key = matching_key(line)
        if any(label in key for label in ("chan doan", "chn doan")):
            value = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
            if value and matching_key(value) != "chan doan":
                diagnosis = value
        if any(label in key for label in ("benh kem theo", "bnh kem theo", "benh nen", "bnh nen", "benh phu")):
            value = re.split(r"[:：]", line, maxsplit=1)[-1].strip(" ;:,-")
            # ICD codes and Vietnamese text are often separated by semicolons.
            parts = [part.strip(" ;:,-") for part in re.split(r"[;|]", value) if part.strip(" ;:,-")]
            for part in parts:
                if re.fullmatch(r"[A-Za-z]\d{1,3}(?:\.\d+)?", part):
                    icd_codes.append(part.upper())
                elif len(part) > 2:
                    conditions.append(part)
            # If the label occupies its own OCR box, use the following line.
            if not value and index + 1 < len(lines):
                next_line = lines[index + 1].strip(" ;:,-")
                if next_line:
                    conditions.append(next_line)
    return {
        "diagnosis": diagnosis,
        "underlying_conditions": list(dict.fromkeys(conditions)),
        "icd_codes": list(dict.fromkeys(icd_codes)),
    }
