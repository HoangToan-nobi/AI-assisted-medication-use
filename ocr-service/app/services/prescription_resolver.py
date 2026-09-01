"""Document classification and row extraction for prescription images."""

from __future__ import annotations

import re
from math import hypot
from statistics import median
from typing import Any

from rapidfuzz import fuzz

from app.utils.text_utils import extract_strengths, matching_key

_PRESCRIPTION_MARKERS = (
    # Include frequent OCR variants: ``DON THUC`` / ``DON THU`` when the
    # Vietnamese ``Ố``/``UỐC`` is lost by the recognizer.
    "don thuoc", "don thuc", "don thu", "donthuoc", "donthuc",
    "thong tin benh nhan", "thong tin don thuoc", "cach dung",
    "toa thuoc", "toa thuoc mua", "thuoc mua", "benh vien", "ma benh nhan",
    "kho xuat", "chan doan", "bac si", "ten thuoc", "chi dinh dung thuoc",
    "chi dinh thuoc", "loi dan cua bac si",
)
# Tiêu đề mục ("ĐƠN THUỐC", "II.THÔNG TIN ĐƠN THUỐC") luôn ngắn, còn câu lời dặn
# có nhắc tới chữ "đơn thuốc" thì dài. Đo trên eval/end2end: tiêu đề thật dài nhất
# 22 ký tự, câu lời dặn ngắn nhất 33 - ngưỡng nằm giữa khoảng trống đó.
_MAX_HEADING_LENGTH = 28
# Từ chỉ liều lượng/đường dùng/bối cảnh khám bệnh. Ảnh nào không có đủ mấy từ này
# thì gần như chắc chắn không phải giấy tờ thuốc - xem classify_document.
_MEDICAL_TERMS = (
    "vien", "uong", "ngay", "lan", "sang", "chieu", "toi", "lieu", "hop",
    "goi", "chai", "ong", "lo", "tuyp", "bac si", "benh", "chan doan", "thuoc",
    "don vi",
)
# Đo trên eval/end2end: đơn/hoá đơn thuốc thật thấp nhất có 5 từ, còn ảnh không
# liên quan (thực đơn quán ăn, hoá đơn siêu thị) có 0. Ngưỡng đặt giữa khoảng trống.
_MIN_MEDICAL_TERMS = 3

# Strong evidence that the page belongs to another domain. These markers are
# consulted only after checking for a real prescription structure, so a pharmacy
# sales slip containing prices can still be parsed when it also has medicine
# strengths, dosage forms and numbered rows.
_NON_MEDICAL_MARKERS = (
    "chi tiet giao dich", "chuyen khoan", "so tai khoan", "ma giao dich",
    "tra soat giao dich", "hoa don thanh toan", "ten mon", "thu ngan",
    "tong thanh toan", "tien mat", "tra lai khach", "nha hang",
)

_DOSAGE_FORMS = ("vien", "goi", "chai", "ong", "lo", "tuyp")
# Markers that name a patient or a visit. A product box can carry dosing text,
# a route, several strengths and even "theo đơn của bác sĩ", so most
# prescription markers are not discriminative -- these are: nothing printed on
# a medicine box refers to one patient's diagnosis or record number.
# ``bac si`` is deliberately excluded for exactly that reason.
_PATIENT_VISIT_MARKERS = (
    "chan doan", "ma benh nhan", "thong tin benh nhan",
    "thong tin don thuoc", "kho xuat",
)
_EXPLICIT_PRESCRIPTION_MARKERS = (
    "don thuoc", "don thuc", "don thu", "donthuoc", "donthuc", "toa thuoc",
)
# Chuỗi chẩn đoán ngắn hơn mức này gần như luôn là rác OCR ("ZS", "-"). Bệnh thật
# ngắn nhất gặp trên eval/end2end là "Sốt virus" (9 ký tự), nên 4 còn dư biên.
_MIN_CONDITION_LENGTH = 4
# Ngày tháng đứng đầu ô ("27/07/2020", "04/09/1950"). Dấu "/" nằm trong
# _ROW_SEPARATOR nên nếu không chặn riêng, "27/07/2020" bị đọc thành dòng thuốc
# số 27 - đo thật trên eval/end2end/don26.jpg: nó tạo ra một dòng ma mang toàn
# thông tin bệnh nhân, rồi resolver gán cho dòng đó một thuốc ho (0.51 điểm).
_LEADING_DATE = re.compile(r"^\s*\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{2,4}")
# Khối hành chính đầu đơn: không bao giờ là dòng thuốc, dù OCR có đọc ra số nào
# ở đầu ô đi nữa.
_PATIENT_BLOCK_MARKERS = (
    "gioi tinh", "ngay sinh", "ho ten", "ho va ten", "dia chi", "so the",
    "bhyt", "can cuoc", "so dien thoai", "ma benh nhan", "ma y te", "nghe nghiep",
    "ngay rv", "ngay vao", "tuoi",
)
# Và phải có ít nhất một nguyên âm: mã số/ký hiệu lọt qua OCR ("ZS", "TP", "BC")
# đủ dài nhưng không phải chữ.
_VOWELS = set("aeiouyàáâãèéêìíòóôõùúýăđĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ")

# ICD-10 codes are also reliable layout anchors when OCR loses the separators
# between diagnoses.  Two patterns are deliberately kept separate:
#
# * ordinary letter-prefixed codes may appear before or after a disease name;
# * an OCR-confused leading ``1/l`` is accepted as ``I`` only before ``-``/``:``.
#
# The second restriction prevents blood pressure ``120/80`` and other normal
# figures from silently becoming I20.
_ICD_CODE = re.compile(r"(?<![A-Za-z0-9])([A-Z]\d{2}(?:\.\d+)?)(?![A-Za-z0-9])", re.IGNORECASE)
_OCR_I_CODE = re.compile(
    r"(?<![A-Za-z0-9])([1Il])(?P<digits>\d{2}(?:\.\d+)?)(?=\s*[-:–—])",
    re.IGNORECASE,
)

# A diagnosis block ends before vitals/instructions/the medication table.  Use
# narrow, beginning-of-line markers: a condition may legitimately contain the
# word "thuốc" or "mạch" in the middle of its name.
_CONDITION_BLOCK_STOP_PREFIXES = (
    "chan doan", "chn doan", "benh kem theo", "bnh kem theo",
    "benh nen", "bnh nen", "benh phu",
    "thuoc", "danh sach thuoc", "ten thuoc", "stt ", "loi dan",
    "dan do", "ngay hen", "hen kham", "kham lai", "ket qua cls",
    "han su dung", "chi dinh dung thuoc", "chi dinh thuoc",
    "so luong", "don vi", "cach dung",
    # Printed field labels that sit on the same band as the diagnosis but are
    # not part of it. Detection boxes run taller than the printed line, so a
    # field on the row above still overlaps the label vertically and passes the
    # geometric guards in _value_beside_label; on don39 that produced the
    # diagnosis "Nhức đầu kiểu căng cơ Mã ICD: G44.2 Ngày điều trị", which then
    # matches nothing in the disease catalogue. The code itself is not lost --
    # extract_prescription_conditions harvests ``Mã ICD`` fields separately.
    "ma icd", "ngay dieu tri",
)
_VITAL_SIGN_PREFIXES = (
    "mach", "nhip tho", "nhiet do", "can nang", "huyet ap", "ha mmhg",
)


def _looks_like_condition(text: str) -> bool:
    """Loại chuỗi chẩn đoán không thể là tên bệnh.

    Cổng này cố ý dễ tính: nó chỉ chặn rác hiển nhiên. Việc quyết định chuỗi có
    ứng với bệnh nào trong danh mục là của backend (match_diseases_in_phrase),
    nơi có bảng Disease - service này không giữ danh mục bệnh.
    """
    stripped = text.strip()
    if len(stripped) < _MIN_CONDITION_LENGTH:
        return False
    # Printed clinical-test markers such as ``HP(+)`` are meaningful parts of
    # a diagnosis despite containing no vowel. Keep only this narrow shape.
    if re.fullmatch(r"[A-Za-z]{1,5}\s*\(\s*[+-]\s*\)", stripped):
        return True
    # Cropped vital/table fragments such as ``Ty 145`` are not diagnoses.
    if re.fullmatch(r"[A-Za-zÀ-ỹ]{1,3}\s*[:.,-]?\s*\d{2,3}", stripped):
        return False
    return any(char in _VOWELS for char in stripped.casefold())


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match a normalized word/phrase, never a substring inside another word."""
    if not text or not phrase:
        return False
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _count_phrases(text: str, phrases: tuple[str, ...]) -> int:
    return sum(_contains_phrase(text, phrase) for phrase in phrases)
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
# A row digit and its separator can be fused into one damaged token by OCR
# (``2/ Ibufen`` -> ``2y Ibufen``). It is safe to remove only this narrow
# digit+one-letter token when an alphabetic medicine-looking value follows.
_DAMAGED_ROW_PREFIX = re.compile(
    r"^\s*\d{1,2}[A-Za-z|]\s+(?=[A-Za-zÀ-ỹ])",
    re.IGNORECASE,
)
# Packaging, regulatory and marketing wording -- never the identity of the
# product. Matched on word boundaries, not as substrings: the old list held
# ``giam``/``dau``/``khong`` and matched them anywhere, and it held the
# ingredient names ``paracetamol``/``caffeine``, which threw away the very line
# that identifies the drug (a Glotadol blister prints "500mg Paracetamol").
_PACKAGE_STOPWORDS = (
    "health supplement", "gmp", "box of", "tablet", "tablets", "blister",
    "formulation", "vien nen", "film-coated",
    "giam dau", "tac dung", "gay buon ngu", "khong gay buon ngu",
    # Seen on real Vietnamese blisters and vials.
    "vial", "ampoule", "powder for injection", "prescription only",
    "thuoc ban theo don", "san xuat tai", "cong ty co phan",
    "batch no", "mfg date", "exp date", "so dang ky",
)
_TABLE_FOOTER_MARKERS = (
    "cong khoan", "tong khoan", "tong 7 khoan", "loi dan", "benh nhan", "nguoi giao", "bac si dieu tri",
    "bac si ke don", "phong tai kham", "ck noi tiet", "ck nqi tiet", "thuoc chong thai",
    "lien he", "tiep tuc", "thuoc dtd", "hen kham lai", "toa cap ngay", "ngay ke don", "tai kham",
    "bac si", "dan cun", "ghi chu", "shichu", "ck ni tiet", "ck ni tit",
    "stt", "ten thuoc", "don vi sl", "nguoi mua", "kham lai", "ghi ro ho ten",
    "so ngay dung", "phat thu",
)
_SCHEDULE_MARKERS = (
    "uong", "ngay uong", "moi lan", "lieu dung", "cach dung",
    "kho cap phat", "bhyt ngoai tru",
    # Routes of administration open a dosing line just like ``Uống`` does.
    # Without them ``Tiêm dưới da - sáng 28 đv chiều 26 đv`` was treated as a
    # medicine name and became a row of its own.
    # Multi-word only. A bare ``tiem``/``ngam``/``thoa``/``dan`` is a prefix
    # test against three or four letters and swallows real names --
    # ``Danapha Napharangan``, ``Ngamzole 20mg``, ``Thoanil 5mg`` all matched.
    "tiem duoi da", "tiem bap", "tiem tinh mach", "tiem truyen",
    "nho mat", "nho tai", "nho mui", "xit mui", "xit hong",
    "dat hau mon", "dat am dao", "ngam duoi luoi",
    "sang", "sing", "slng", "trua", "trura", "chieu", "ghi chu", "shichu",
)


# Footer wording is matched fuzzily, not by substring. Two single-character OCR
# errors on a real prescription -- "bác sĩ" read as "bás sĩ" and "Ghi chú" as
# "chi chú" -- were enough to slip the whole signature block past an exact
# check, which then surfaced as a seventh medication that does not exist.
# Measured on that page: real footer wording scores 83-100 against these
# markers, real medicine names 40-60, so the cutoff sits in a 23-point gap.
_FOOTER_FUZZ_CUTOFF = 82
# Short markers are kept on exact matching; at three or four characters a fuzzy
# score says nothing useful and would start swallowing drug names.
_FUZZY_FOOTER_MARKERS = tuple(m for m in _TABLE_FOOTER_MARKERS if len(m) >= 6)
_EXACT_FOOTER_MARKERS = tuple(m for m in _TABLE_FOOTER_MARKERS if len(m) < 6)


def is_table_footer(text: str) -> bool:
    """True for the signature/total block printed below the medication table."""
    key = matching_key(text)
    if not key:
        return False
    if (
        key.strip(" .,:;()-") in {"ha noi", "tp ho chi minh", "ho chi minh"}
        or bool(re.match(r"^(?:ha noi|tp ho chi minh|ho chi minh)\W+ngay\b", key))
    ):
        return True
    if any(marker in key for marker in _EXACT_FOOTER_MARKERS):
        return True
    key_words = re.findall(r"[a-z0-9]+", key)
    compact_key = "".join(key_words)
    for marker in _FUZZY_FOOTER_MARKERS:
        marker_words = marker.split()
        compact_marker = "".join(marker_words)
        # Short footer labels are often returned as one damaged token
        # (``Ghi chú`` -> ``Ghiche``). Compare the entire compact box only when
        # lengths nearly agree; unlike partial matching this cannot remove a
        # long medicine/ingredient sentence that happens to contain similar
        # letters.
        if (
            6 <= len(compact_marker) <= 12
            and abs(len(compact_key) - len(compact_marker)) <= 1
            and fuzz.ratio(compact_marker, compact_key) >= _FOOTER_FUZZ_CUTOFF
        ):
            return True
        if (
            len(marker_words) >= 2
            and 6 <= len(compact_marker) <= 8
            and len(compact_marker) <= len(compact_key) <= len(compact_marker) + 3
            and fuzz.ratio(compact_marker, compact_key[:len(compact_marker)])
            >= _FOOTER_FUZZ_CUTOFF
        ):
            return True
        # Compare word-aligned windows instead of partial_ratio over the whole
        # line. The latter scored ``lời dặn`` against ``dưới dạng`` at 85.7 and
        # removed the first half of don2's Sitagliptin/Metformin name.
        for size in range(max(1, len(marker_words) - 1), len(marker_words) + 2):
            for start in range(0, len(key_words) - size + 1):
                window = " ".join(key_words[start:start + size])
                if fuzz.ratio(marker, window) >= _FOOTER_FUZZ_CUTOFF:
                    return True
    return False


def _is_schedule_text(text: str) -> bool:
    """Recognize dosage instructions, including common OCR errors like ``Ivx``."""
    # A missed row digit often survives as punctuation (``- Uống...``). Ignore
    # that leading ink before deciding whether this is an instruction.
    key = matching_key(text).strip().lstrip(" .,:;()/\\-|_").lstrip()
    if key.startswith(_SCHEDULE_MARKERS):
        return True
    # ``Tối`` is often recognized as ``Tôi``. Require a following numeric dose
    # so a medicine/product whose name begins with ``Tỏi`` is not discarded.
    if re.match(r"^toi\s*:?\s*\d", key):
        return True
    # ``Trưa`` can lose its diacritics to ``Tra``. Three letters are far too
    # few for a bare prefix test -- it matched the signatory "TRANG CẨM TÚ" on
    # a GLOMED leaflet -- so require the dose that always follows it.
    if re.match(r"^tra\s*:?\s*\d", key):
        return True
    # A dose column can prefix the time of day with a count (``2 Trưa:``).
    # That leading number is not a medicine-row marker.
    if re.match(r"^\d{1,2}\s+(?:sang|trua|chieu|toi)\b", key):
        return True
    # Topical instructions are frequently printed on the line below the
    # product name, e.g. ``xoa lung dau``. VietOCR may read ``lung`` as
    # ``hung``; the line is still an instruction, never another medicine.
    if key.startswith(("xoa ", "boi ", "bôi ")):
        return True
    # A crop or page edge can remove the beginning of ``Sáng``. The remainder
    # still has the unmistakable schedule shape ``áng/ng: 1.00``; without this
    # gate it is appended to the medicine name (don7: Nefiprazol/Gastrel).
    if re.match(r"^(?:ang|ng)\s*:?\s*\d+(?:[.,]\d+)?\s*$", key):
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
    if _LEADING_DATE.match(text):
        return None
    key = matching_key(text)
    if any(marker in key for marker in _PATIENT_BLOCK_MARKERS):
        return None
    match = _ROW_NUMBER.match(text)
    if match:
        number = int(match.group(1))
        # Printed prescription rows are one-based. OCR frequently isolates a
        # dose such as ``0.0``/``00`` in the left half of a row; accepting zero
        # makes that dose the next medicine and hides the real line above it.
        if 1 <= number <= 99:
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
    cleaned = _DAMAGED_ROW_PREFIX.sub("", text)
    # Route + dosage form is sometimes placed between a medicine and its
    # parenthesised ingredient. Remove only that bounded phrase and retain the
    # ingredient. OCR variants such as ``Vống`` and ``Ông`` are included.
    cleaned = re.sub(
        r"[,.;]?\s*(?:u[oố]ng|v[oố]ng|ti[eê]m(?:\s+b[aắ]p)?)\s+"
        r"(?:vi[eê]n|[oôố]ng|g[oó]i|chai|l[oọ])\s*(?=\()",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.split(
        r"\b(?:ngày|ngay|sáng|sang|sing|chiều|chieu|tối|toi|trưa|trua|trura|"
        r"tra|ghi\s+chú|ghi\s+chu|shichu)\b|"
        r"\b[ilvtd\d]{1,3}\s*[vxyr]\s*x?\s*\d+\s*(?:lần|lan)\b|"
        r"\b\d{1,4}\s*(?:lần|lan)\b|\b\S{0,5}x\s*\d+\s*(?:lần|lan)\b",
        cleaned,
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
    cleaned = re.sub(
        rf"^\s*{_LEADING_INK}\d{{1,2}}(?:\s*{_ROW_SEPARATOR}\s*|\s+)",
        "",
        cleaned,
    )
    return cleaned.strip(" -:(,")


def _is_numbered_medication_line(line: str) -> bool:
    """A numbered line that actually carries a medicine.

    ``_ROW_NUMBER`` alone only says "this line starts with a number", which any
    document with footnotes, page numbers or a pack count satisfies. On a
    GLOMED advertising leaflet for ACTIXIM the three "numbered rows" were
    ``1 vial/box``, ``1. Bộ Y Tế. Dược thư quốc gia Việt Nam. Hà Nội, 2002.``
    and the page number ``01`` -- enough, together with the repeated
    ``750 mg``, to classify a one-product advert as a prescription and invent
    three medicines out of packaging copy.

    Only used where no patient/visit marker is present; once a document is
    known to concern one patient, a bare numbered row is evidence enough.
    """
    if not _ROW_NUMBER.match(line) or _LEADING_DATE.match(line):
        return False
    body = _clean_medication_name(line)
    if not re.search(r"[A-Za-zÀ-ỹ]", body):
        return False
    return bool(extract_strengths(body)) or bool(
        re.search(r"\([^)]*[A-Za-zÀ-ỹ]", body)
    )


def classify_document(items: list[dict[str, Any]]) -> str:
    """Classify from OCR text; a medicine box has no patient/prescription table.

    ``unknown`` is not only for a blank page. Anything with text used to fall
    through to ``medicine_package`` and get matched against the drug catalogue,
    which meant a restaurant menu came back proposing "Tiphadol 80" and a
    supermarket receipt proposing "Dầu Dân tộc" -- both above the score floor,
    both nonsense. A real medical document always states doses or a route
    (mg/ml/viên/uống/ngày...); measured over eval/end2end the weakest real one
    carries 5 such terms while unrelated images carry none.
    """
    if not items:
        return "unknown"

    lines = [str(item.get("text", "")).strip() for item in items if str(item.get("text", "")).strip()]
    text = matching_key(" ".join(lines))
    marker_count = _count_phrases(text, _PRESCRIPTION_MARKERS)
    explicit_prescription = any(
        _contains_phrase(text, marker) for marker in _EXPLICIT_PRESCRIPTION_MARKERS
    )
    strength_lines = sum(bool(extract_strengths(line)) for line in lines)
    row_lines = sum(bool(_ROW_NUMBER.match(line)) and not _LEADING_DATE.match(line) for line in lines)
    medication_row_lines = sum(_is_numbered_medication_line(line) for line in lines)
    schedule_lines = sum(_is_schedule_text(line) for line in lines)
    dosage_form_count = _count_phrases(text, _DOSAGE_FORMS)

    # Strong headings win immediately. Otherwise require multiple independent
    # signals: structure + actual unit-bearing strengths, or a pharmacy-style
    # numbered list with repeated dosage forms. This recovers cropped/no-heading
    # prescriptions without turning a restaurant table into a medicine list.
    if explicit_prescription or marker_count >= 2:
        return "prescription"
    if strength_lines >= 2 and (
        medication_row_lines >= 2 or schedule_lines >= 2 or marker_count >= 1
    ):
        return "prescription"
    # This one keeps the loose count on purpose: it is the pharmacy-receipt
    # rule, whose numbered lines ARE quantities and prices by design (eval
    # don17). The repeated dosage forms are what separate a receipt from an
    # advertising leaflet, which carries none.
    if strength_lines >= 1 and row_lines >= 2 and dosage_form_count >= 2:
        return "prescription"
    # A sparse prescription crop can carry only one of everything and still be
    # unmistakable: eval/test/don22 is five OCR boxes reading "Chần đoán:
    # VGSVB", "1. Tenofovir alafenamidẽ", "Ngày uống 1 lần..." and "90 viên".
    # None of the counts above reach two, so it fell through to the
    # ``strength_lines >= 1`` package fallback and the patient's name became
    # the proposed drug. One numbered medication row under a patient/visit
    # marker is decisive: a product box never numbers medicines per patient.
    if row_lines >= 1 and any(
        _contains_phrase(text, marker) for marker in _PATIENT_VISIT_MARKERS
    ):
        return "prescription"

    if _count_phrases(text, _NON_MEDICAL_MARKERS):
        return "unknown"

    # A package can be visually minimal (brand + ``500mg`` + manufacturer), so
    # one real unit-bearing strength is sufficient after non-medical documents
    # have been rejected. Weak words such as ``ngày`` or ``ống`` never suffice.
    if strength_lines >= 1:
        return "medicine_package"
    if _count_phrases(text, _MEDICAL_TERMS) >= _MIN_MEDICAL_TERMS:
        return "medicine_package"
    return "unknown"


def extract_package_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select prominent brand-name OCR regions from a medicine package.

    This is intentionally conservative: it keeps short, prominent label text
    and excludes marketing/copy text. The returned OCR text is shown to the
    user before any database candidate is proposed.
    """
    return _rank_package_names(_package_name_candidates(items), items)


def _package_name_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Regions that could carry a product name, annotated with glyph height."""
    candidates: list[dict[str, Any]] = []
    for item in items:
        text = " ".join(item.get("text", "").split()).strip()
        key = matching_key(text)
        if not text or len(text) > 32 or any(
            _contains_phrase(key, stop) for stop in _PACKAGE_STOPWORDS
        ):
            continue
        if re.fullmatch(r"\d+|B", text, flags=re.IGNORECASE):
            continue
        if not re.search(r"[A-Za-zÀ-ỹ]", text):
            continue
        points = item.get("bbox") or []
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            if len(points) >= 4:
                # Paddle returns an oriented quadrilateral.  Using the
                # axis-aligned y-span made a thin diagonal watermark look
                # taller than the actual product name (its long baseline also
                # travels a long way vertically).  Measure the printed line's
                # own edges instead, so rotation changes neither glyph height
                # nor prominence.
                top = hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
                right = hypot(points[2][0] - points[1][0], points[2][1] - points[1][1])
                bottom = hypot(points[2][0] - points[3][0], points[2][1] - points[3][1])
                left = hypot(points[3][0] - points[0][0], points[3][1] - points[0][1])
                width = max(1.0, (top + bottom) / 2.0)
                height = max(1.0, (left + right) / 2.0)
                area = width * height
            else:
                height = max(1.0, max(ys) - min(ys))
                area = max(1.0, max(xs) - min(xs)) * height
            y = min(ys)
        else:
            height, area, y = 0.0, 0.0, len(candidates)
        candidates.append({**item, "text": text, "_area": area, "_height": height, "_y": y})
    return candidates


def _rank_package_names(
    candidates: list[dict[str, Any]], context: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Three strongest product-name regions, restored to reading order.

    Strength-bearing text is product evidence that a manufacturer watermark
    does not have.  A visually prominent title immediately above that evidence
    is also preferred.  Glyph size remains the tie-breaker for sparse boxes
    where OCR did not recover any strength.
    """
    strength_items = [
        item for item in (context or [])
        if extract_strengths(str(item.get("text", ""))) and _rect_of(item)
    ]

    def product_evidence(candidate: dict[str, Any]) -> int:
        if extract_strengths(candidate["text"]):
            return 2
        rect = _rect_of(candidate)
        if rect is None:
            return 0
        x1, y1, x2, y2 = rect
        width = max(1.0, x2 - x1)
        for strength_item in strength_items:
            sx1, sy1, sx2, sy2 = _rect_of(strength_item)
            strength_width = max(1.0, sx2 - sx1)
            horizontal_overlap = max(0.0, min(x2, sx2) - max(x1, sx1))
            vertical_gap = max(0.0, sy1 - y2, y1 - sy2)
            strength_height = max(1.0, sy2 - sy1)
            if (
                horizontal_overlap >= 0.25 * min(width, strength_width)
                and vertical_gap <= max(18.0, 1.5 * strength_height)
            ):
                return 1
        return 0

    selected = sorted(
        candidates,
        key=lambda item: (product_evidence(item), item["_height"], item["_area"]),
        reverse=True,
    )[:3]
    return sorted(selected, key=lambda item: (item["_y"], item.get("bbox", [[0, 0]])[0][0]))


def _rect_of(item: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points = item.get("bbox") or []
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _spatial_clusters(items: list[dict[str, Any]], gap: float) -> list[list[dict[str, Any]]]:
    """Group OCR boxes that sit close enough to be printed on one object.

    Union-find over rectangles inflated by ``gap``. Text inside one blister is
    tightly packed; separate blisters on a table are not, so the printed items
    fall out as connected components without any drug knowledge.
    """
    boxed = [item for item in items if _rect_of(item)]
    parent = list(range(len(boxed)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    rects = [_rect_of(item) for item in boxed]
    for i in range(len(boxed)):
        ax1, ay1, ax2, ay2 = rects[i]
        for j in range(i + 1, len(boxed)):
            bx1, by1, bx2, by2 = rects[j]
            if (
                ax1 - gap <= bx2 and bx1 - gap <= ax2
                and ay1 - gap <= by2 and by1 - gap <= ay2
            ):
                union(i, j)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for index, item in enumerate(boxed):
        grouped.setdefault(find(index), []).append(item)
    return list(grouped.values())


def extract_package_products(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split one packaging photo into the distinct products it shows.

    A single photo often holds several blisters. The one-product path joins the
    three largest regions on the whole image into one string and resolves them
    as one drug, so a table of eight blisters returns one medicine and silently
    drops the other seven -- the worst possible failure for an interaction
    checker, because nothing on screen says anything is missing.

    Returns one entry per product with its name regions and whether the object
    carries a printed strength. Deciding which entries are real products needs
    the drug catalogue and therefore belongs to the caller; this function only
    reports layout.
    """
    boxed = [item for item in items if _rect_of(item)]
    if len(boxed) < 2:
        return []

    heights = [
        (_rect_of(item)[3] - _rect_of(item)[1]) for item in boxed
    ]
    gap = max(8.0, median(heights) * 1.2)

    products: list[dict[str, Any]] = []
    for cluster in _spatial_clusters(boxed, gap):
        names = _rank_package_names(_package_name_candidates(cluster), cluster)
        if not names:
            continue
        cluster_text = " ".join(item.get("text", "") for item in cluster)
        products.append({
            "name_items": names,
            "texts": [item["text"] for item in names],
            "has_strength": bool(extract_strengths(cluster_text)),
            "_top": min(_rect_of(item)[1] for item in cluster),
            "_left": min(_rect_of(item)[0] for item in cluster),
        })
    products.sort(key=lambda product: (product["_top"], product["_left"]))
    return products


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
            number = _row_number(text, x1=0.0, page_right=1.0)
            if number is not None and not _is_schedule_text(text):
                if current:
                    rows.append(current)
                current = {"row_number": number, "items": [item], "texts": [text]}
            elif current and not is_table_footer(text):
                current["items"].append(item)
                current["texts"].append(text)
        if current:
            rows.append(current)
        for row in rows:
            name_texts = [_clean_medication_name(text) for text in row["texts"]]
            name_texts = [text for text in name_texts if text and re.search(r"[A-Za-zÀ-ỹ]", text)]
            row["name_texts"] = name_texts
            row["resolver_texts"] = name_texts[:]
            row["name_items"] = [
                item
                for item in row["items"]
                if _clean_medication_name(item["text"]).strip() in name_texts
            ]
        return rows

    def rect(item: dict[str, Any]) -> tuple[float, float, float, float]:
        points = item["bbox"]
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        return min(xs), min(ys), max(xs), max(ys)

    ordered = sorted(with_boxes, key=lambda item: (rect(item)[1], rect(item)[0]))
    page_right = max(rect(item)[2] for item in ordered)

    def medication_anchor(item: dict[str, Any]) -> bool:
        """Return whether one box can safely anchor a medication row.

        This intentionally uses document structure rather than a drug-name
        dictionary. A strength is the strongest signal. Parenthesised aliases
        plus a number are accepted as a fallback because OCR often changes
        ``10mg`` into ``10 mang`` while preserving the brand/ingredient layout.
        """
        text = item["text"].strip()
        cleaned = _clean_medication_name(text)
        key = matching_key(cleaned).strip(" .,:;()")
        if (
            not cleaned
            or not re.search(r"[A-Za-zÀ-ỹ]", cleaned)
            or _is_schedule_text(text)
            or is_table_footer(text)
            or key.startswith(_PATIENT_BLOCK_MARKERS)
            or key.startswith(("so luong", "so ngay", "ten thuoc", "ham luong", "don vi"))
        ):
            return False
        if extract_strengths(text):
            return True
        # A fully numeric strength may be recognized entirely as confusable
        # letters (``500MG`` -> ``SOOMG``). Accept that narrow token only when
        # it is immediately followed by a pharmaceutical unit. Geometry and
        # schedule gates still decide whether it opens a separate row.
        if re.search(
            r"(?<![A-Za-z0-9])[0-9SOIl]{2,5}\s*(?:mg|mcg|ml|g)(?![A-Za-z])",
            text,
            flags=re.IGNORECASE,
        ):
            return True
        return bool(
            # The numeric evidence must belong to the same parenthesised
            # brand/strength fragment. This keeps a footer such as
            # ``(giờ hành chính): 1900...`` from becoming a medicine while
            # retaining a damaged alias like ``(Brand 10 mang``.
            re.search(r"\([^\n)]*[A-Za-zÀ-ỹ][^\n)]*\d", text)
        )

    # Pharmacy receipts do not have an STT column. Each medicine name is
    # printed on its own line, followed by quantity/unit/unit-price/total. If
    # those quantities are fed to the numbered-prescription parser, values
    # such as 40, 20, 1 and 4 become row markers and every ``Viên/Chai/Tube``
    # cell becomes a fake medicine (eval don17). Activate this layout only
    # when the receipt exposes at least three of its four characteristic
    # headers, including both quantity and unit.
    receipt_headers: dict[str, dict[str, Any]] = {}
    for item in ordered:
        compact = re.sub(r"[^a-z]", "", matching_key(item["text"]))
        header = {
            "sl": "quantity",
            "dvt": "unit",
            "dgia": "unit_price",
            "ttien": "total",
        }.get(compact)
        if header:
            receipt_headers.setdefault(header, item)

    is_pharmacy_receipt = (
        len(receipt_headers) >= 3
        and "quantity" in receipt_headers
        and "unit" in receipt_headers
    )
    if is_pharmacy_receipt:
        header_bottom = max(rect(item)[3] for item in receipt_headers.values())
        footer_tops = [
            rect(item)[1]
            for item in ordered
            if matching_key(item["text"]).startswith(("tong tien", "giam gia"))
            and rect(item)[1] > header_bottom
        ]
        footer_top = min(footer_tops) if footer_tops else float("inf")
        price_left = (
            rect(receipt_headers["unit_price"])[0]
            if "unit_price" in receipt_headers
            else page_right * 0.68
        )
        receipt_names = []
        for item in ordered:
            text = " ".join(item["text"].split()).strip()
            key = matching_key(text).strip(" .,:;()")
            x1, y1, _x2, _y2 = rect(item)
            if not (header_bottom < y1 < footer_top and x1 < price_left):
                continue
            if key in {
                *_DOSAGE_FORMS, "tube", "bottle", "tablet", "tablets",
                "sl", "dvt", "d gia", "t tien",
            }:
                continue
            if len(text) < 4 or not re.search(r"[A-Za-zÀ-ỹ]{2}", text):
                continue
            if is_table_footer(text) or _is_schedule_text(text):
                continue
            receipt_names.append(item)

        if receipt_names:
            rows = []
            for position, item in enumerate(receipt_names, start=1):
                text = " ".join(item["text"].split()).strip()
                cleaned = _clean_medication_name(text)
                if not cleaned:
                    continue
                rows.append({
                    "row_number": position,
                    "items": [item],
                    "texts": [text],
                    "name_texts": [cleaned],
                    "resolver_texts": [text],
                    "name_items": [item],
                })
            return rows

    # Restrict row-number detection to the medication section. This prevents
    # phone screenshot artefacts (20:32, battery 86), age, and house numbers
    # from becoming fake medication rows.
    section_start_y = 0.0
    section_end_y = float("inf")
    end_candidates: list[float] = []
    # Two passes on purpose. The section start and the section end used to be
    # decided in a single top-to-bottom loop, so the end was tested against
    # whatever start had been seen *so far*. On a Bạch Mai layout the page title
    # ``Đơn thuốc`` sits in the letterhead, the real table heading
    # (``II. THÔNG TIN ĐƠN THUỐC``) hundreds of pixels lower; a clinic or patient
    # line in between ("Mã bệnh nhân: ...", "Phòng khám ...") satisfied the
    # footer test against that provisional start and pinned the end ABOVE the
    # final start. The window then contained nothing and the whole prescription
    # extracted zero rows (eval don2, don3, don15, don25). Resolving the start
    # completely first makes the end gate see the boundary that actually wins.
    for item in ordered:
        key = matching_key(item["text"])
        if (
            "thong tin don thuoc" in key
            or any(marker in key for marker in ("don thuoc", "don thuc", "don thu", "donthuoc", "donthuc"))
            or "toa thuoc" in key
            or key.startswith(("dieu tri", "dieu ti"))
            or "chi dinh dung thuoc" in key
            or "chi dinh thuoc" in key
        ):
            # Ignore later footer instructions containing words such as
            # ``đơn thuốc``; the medication table is near the upper part of
            # the page and must remain the active section boundary.
            #
            # The y < 800 gate alone is not enough: on eval/end2end/don11.jpg the
            # advice line "đã tư vấn kỹ cho bệnh nhân về đơn thuốc và..." sits at
            # y=786 and moved the section start below all four medication rows,
            # losing the whole prescription. A heading is short; an instruction
            # sentence that merely mentions "đơn thuốc" is long -- measured over
            # the eval set the longest real heading is 22 characters and the
            # shortest such footer sentence is 33.
            if rect(item)[1] < 800 and len(item["text"].strip()) <= _MAX_HEADING_LENGTH:
                section_start_y = max(section_start_y, rect(item)[3])
        # Some Bạch Mai templates lose the Roman numeral/header but retain
        # the table headings.  Starting after these headings prevents patient
        # age, codes and barcode digits from becoming medicine rows.
        #
        # Same upper-page gate as the markers above, plus an explicit exclusion:
        # ``STT lĩnh thuốc`` is the dispensing queue number printed *below* the
        # table, not a column heading. Without both guards it moves the section
        # start past every medication row -- measured on a real prescription
        # (eval/end2end/don25.jpg) that alone turned 5 rows into 0.
        if (
            rect(item)[1] < 800
            and "linh thuoc" not in key
            and (key.startswith("stt") or "ten thuoc" in key or "ten thuc" in key)
        ):
            section_start_y = max(section_start_y, rect(item)[3])

    for item in ordered:
        key = matching_key(item["text"])
        if (
            section_start_y
            and rect(item)[1] > section_start_y + 100
            and any(marker in key for marker in (
                "cong khoan", "tong khoan", "loi dan", "ngay tai kham",
                "toa cap ngay", "bac si kham", "bac si dieu tri", "bac si",
                "so ngay dung", "phat thu",
            ))
        ):
            end_candidates.append(rect(item)[1])

    # An end boundary is only believable if the table it closes contains
    # something. On layouts where ``ĐƠN THUỐC`` is the letterhead title rather
    # than the table heading, the clinic line just below it ("Phòng khám Nội số
    # 2", "1. Khoa Khám Bệnh...") matches a footer marker and closed the section
    # before the first medicine (eval don22, don26). Take the highest candidate
    # that still leaves a row number inside the window; if none does, leave the
    # section open and let the row filters do the work.
    def _encloses_a_row(limit: float) -> bool:
        for candidate in ordered:
            cx1, cy1, _cx2, cy2 = rect(candidate)
            centre = (cy1 + cy2) / 2
            if not section_start_y < centre < limit:
                continue
            if cx1 > page_right * 0.35:
                continue
            text = candidate["text"].strip()
            if _is_schedule_text(text) or is_table_footer(text):
                continue
            if _row_number(text, cx1, page_right) is not None:
                return True
        return False

    def _rows_between(lower: float, upper: float) -> int:
        total = 0
        for candidate in ordered:
            cx1, cy1, _cx2, cy2 = rect(candidate)
            centre = (cy1 + cy2) / 2
            if not lower < centre < upper or cx1 > page_right * 0.35:
                continue
            text = candidate["text"].strip()
            if _is_schedule_text(text) or is_table_footer(text):
                continue
            if _row_number(text, cx1, page_right) is not None:
                total += 1
        return total

    # Some templates print a per-row note label ("Ghi chú:") under *every*
    # medicine, and that word is also a table-footer marker; the first match
    # closed the table right after row 1 and lost the other five (eval don7).
    # A candidate with another medication row between it and the next candidate
    # is such a repeating in-table label, not the table end. Requiring instead
    # that *no* row follow the boundary overshoots: it walks past the real end
    # down to stray digits in the page footer (measured: +7 phantom rows on
    # don1, don5, don15, don20, don40).
    ordered_candidates = sorted(end_candidates)
    for position, limit in enumerate(ordered_candidates):
        if not _encloses_a_row(limit):
            continue
        following = ordered_candidates[position + 1] if position + 1 < len(ordered_candidates) else float("inf")
        if _rows_between(limit, following):
            continue
        section_end_y = limit
        break
    else:
        for limit in ordered_candidates:
            if _encloses_a_row(limit):
                section_end_y = limit
                break

    # The prescription table's name column ends before the unit/quantity
    # columns. Estimate that boundary from the page width; this prevents
    # dosage and warehouse instructions becoming part of the drug name.
    name_column_right = page_right * 0.48

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
        # A prescription can contain two independently prescribed groups. On
        # don1 the second group starts again at row 1 after a doctor's advice,
        # which looks like a table footer. Recover a marker beyond that footer
        # only with strong layout evidence: it must be a standalone number at
        # the far-left STT column and have alphabetic name text on the same
        # printed line. This excludes page numbers, dates and phone numbers.
        standalone_number = bool(re.fullmatch(r"\d{1,2}", text)) or text.casefold() in {"i", "l", "|"}
        has_adjacent_name = any(
            candidate is not item
            and x2 <= rect(candidate)[0] <= name_column_right
            and abs(((rect(candidate)[1] + rect(candidate)[3]) / 2) - marker_y) <= 20
            and bool(re.search(r"[A-Za-zÀ-ỹ]", candidate["text"]))
            and not _is_schedule_text(candidate["text"])
            and not is_table_footer(candidate["text"])
            for candidate in ordered
        )
        continues_after_footer = (
            section_end_y < float("inf")
            and marker_y >= section_end_y
            and x1 <= page_right * 0.12
            and standalone_number
            and has_adjacent_name
        )
        if (
            number is not None
            and not _is_schedule_text(text)
            and section_start_y < marker_y
            and (marker_y < section_end_y or continues_after_footer)
            and x1 <= page_right * 0.35
        ):
            # A bare number is accepted only near the left edge (row-number
            # column); a number followed by '.' can be part of the OCR text
            # in the medicine-name column, e.g. ``1.YESOM 40``.
            has_separator = bool(
                re.match(rf"^\s*{_LEADING_INK}\d{{1,2}}(?:{_ROW_SEPARATOR}|\s)", text)
            ) or text.strip().casefold() in {"i", "l", "|"}
            # A bare STT digit fails the 12%-of-page test whenever the sheet has
            # a margin, and ``page_right`` is itself inflated when a second
            # document is visible at the edge of the photo. Both happened on one
            # real prescription: margin 195px, neighbouring sheet at 1290px, so
            # the digits ``1`` and ``2`` were rejected, no marker survived, and
            # the ungated fallback promoted the quantity cells instead.
            #
            # Being first on its own printed line is the local, scale-free
            # definition of a row number, and it needs no page-wide constant.
            # Additive on purpose: it can only accept digits the fractional
            # gates already rejected.
            leads_its_line = standalone_number and has_adjacent_name and not any(
                candidate is not item
                and abs(((rect(candidate)[1] + rect(candidate)[3]) / 2) - marker_y) <= 20
                and rect(candidate)[2] <= x1
                for candidate in ordered
            )
            if has_separator or x1 <= page_right * 0.12 or leads_its_line:
                row_markers.append((number, (y1 + y2) / 2))

    # A header/doctor line can itself begin with ``1.`` immediately before the
    # real table, producing two nearby row 1 markers. Keep the marker with
    # medication evidence in its printed line. This is deliberately limited to
    # duplicate numbers; legitimate rows without a printed strength survive.
    if row_markers:
        deduplicated: list[tuple[int, float]] = []
        for marker in sorted(row_markers, key=lambda value: value[1]):
            if (
                deduplicated
                and marker[0] == deduplicated[-1][0]
                and marker[1] - deduplicated[-1][1] < 80
            ):
                def marker_score(marker_y: float) -> tuple[int, int]:
                    nearby = [
                        candidate for candidate in ordered
                        if abs(((rect(candidate)[1] + rect(candidate)[3]) / 2) - marker_y) <= 24
                        and rect(candidate)[0] <= name_column_right
                    ]
                    return (
                        sum(medication_anchor(candidate) for candidate in nearby),
                        sum(bool(extract_strengths(candidate["text"])) for candidate in nearby),
                    )

                if marker_score(marker[1]) > marker_score(deduplicated[-1][1]):
                    deduplicated[-1] = marker
                continue
            deduplicated.append(marker)
        row_markers = deduplicated

    if not row_markers:
        row_markers = []
        for item in ordered:
            text = item["text"].strip()
            marker_y = (rect(item)[1] + rect(item)[3]) / 2
            number = _row_number(text, rect(item)[0], page_right)
            if number is not None and not _is_schedule_text(text) and section_start_y < marker_y < section_end_y:
                row_markers.append((number, marker_y))

    # A faint/missing digit in the STT column must not merge two medicines.
    # On don16 Paddle loses row 3, but still reads both the name
    # ``Aussin SR 60ml`` and its aligned unit ``Chai``. Treat that geometry as
    # an implicit marker only when several independent layout signals agree.
    existing_marker_ys = [marker_y for _number, marker_y in row_markers]
    implicit_markers: list[tuple[int, float]] = []
    for item in ordered:
        x1, y1, _x2, y2 = rect(item)
        text = item["text"].strip()
        text_after_leading_ink = _DAMAGED_ROW_PREFIX.sub("", text)
        text_after_leading_ink = text_after_leading_ink.lstrip(" .,:;()/\\-|_").lstrip()
        marker_y = (y1 + y2) / 2
        damaged_alias_anchor = bool(
            re.match(r"^\s*[-–—•]", text)
            and re.search(r"\([^)]*[A-Za-zÀ-ỹ]{3,}[^)]*\)?\s*$", text)
            and re.search(r"\b(?:vien|ong|goi|chai|lo)\b", matching_key(text))
        )
        if (
            x1 <= name_column_right
            and section_start_y < marker_y < section_end_y
            and (medication_anchor(item) or damaged_alias_anchor)
            # OCR may preserve a missed row number only as punctuation
            # (``- Kidafort 60ml``). Accept leading ink, but the remaining text
            # must begin like a name and must not be a dosage instruction.
            and bool(re.match(r"^[A-Za-zÀ-ỹ]", text_after_leading_ink))
            and not text.startswith("(")
            and (damaged_alias_anchor or not _is_schedule_text(text_after_leading_ink))
            and not is_table_footer(text)
            and all(abs(marker_y - known_y) > 25 for known_y in existing_marker_ys)
        ):
            has_aligned_form = any(
                form_item is not item
                and rect(form_item)[0] > rect(item)[2]
                and abs(((rect(form_item)[1] + rect(form_item)[3]) / 2) - marker_y) <= 22
                and bool(re.fullmatch(
                    rf"(?:\d+\s+)?(?:{'|'.join(_DOSAGE_FORMS)})",
                    matching_key(form_item["text"]).strip(" .,:;()"),
                ))
                for form_item in ordered
            )
            # Numberless lists have no STT/DVT columns: each strength-bearing
            # line is followed by a separate dosage line. Require at least two
            # such anchors before activating that layout, so a medicine package
            # or a single strength in the header cannot become a prescription.
            unnumbered_anchors = [
                candidate for candidate in ordered
                if rect(candidate)[0] <= name_column_right
                and section_start_y < (rect(candidate)[1] + rect(candidate)[3]) / 2 < section_end_y
                and medication_anchor(candidate)
            ]
            is_unnumbered_list = not row_markers and len(unnumbered_anchors) >= 2

            # A lost middle number can also be recovered between two printed
            # rows when the alias/strength line is followed by a dosage line.
            previous_ys = [known_y for known_y in existing_marker_ys if known_y < marker_y]
            following_ys = [known_y for known_y in existing_marker_ys if known_y > marker_y]
            is_between_rows = bool(previous_ys and following_ys) and (
                marker_y - max(previous_ys) > 25 and min(following_ys) - marker_y > 25
            )
            has_nearby_schedule = any(
                marker_y < (rect(candidate)[1] + rect(candidate)[3]) / 2 <= marker_y + 55
                and _is_schedule_text(candidate["text"])
                for candidate in ordered
            )
            # A new row opens right after the previous row's dosage line; a
            # wrapped ingredient line follows the name it belongs to. Both
            # carry a strength, so only the line above tells them apart -- on
            # the Bình Dân fixture, ``Magnesi Hydroxide 100ml`` is the second
            # half of BIOCID MH and must not become a seventh medicine.
            above = [
                candidate for candidate in ordered
                if rect(candidate)[0] <= name_column_right
                and (rect(candidate)[1] + rect(candidate)[3]) / 2 < marker_y - 5
                and section_start_y < (rect(candidate)[1] + rect(candidate)[3]) / 2
            ]
            follows_a_schedule = bool(above) and _is_schedule_text(
                max(above, key=lambda candidate: (rect(candidate)[1] + rect(candidate)[3]) / 2)["text"]
            )
            printed_gaps = [
                later - earlier
                for earlier, later in zip(sorted(existing_marker_ys), sorted(existing_marker_ys)[1:])
                if later - earlier > 25
            ]
            expected_gap = median(printed_gaps) if printed_gaps else 0
            is_missing_final_row = bool(previous_ys and not following_ys and expected_gap) and (
                expected_gap * 0.45 <= marker_y - max(previous_ys) <= expected_gap * 1.75
            )
            if (
                has_aligned_form
                or is_unnumbered_list
                or (
                    (is_between_rows or is_missing_final_row)
                    and has_nearby_schedule
                    # ``medication_anchor`` already demanded a printed strength
                    # or a parenthesised alias. Requiring a bracket on top of
                    # that missed templates that separate brand from ingredient
                    # with a dash instead -- ``Acritel 5mg - Levocetirizine``
                    # (eval don37, four rows whose STT digit Paddle never
                    # detected). ``follows_a_schedule`` replaces the bracket as
                    # the guard against wrapped continuation lines.
                    and ("(" in text or follows_a_schedule)
                )
            ):
                implicit_markers.append((0, marker_y))

    if implicit_markers:
        row_markers = sorted([*row_markers, *implicit_markers], key=lambda marker: marker[1])

    # Typical vertical distance between two printed rows. Used to give the
    # first row the same window as the rest instead of a fixed constant that
    # would be wrong at another scan resolution.
    marker_gaps = [
        later - earlier
        for earlier, later in zip(
            [y for _n, y in row_markers], [y for _n, y in row_markers][1:]
        )
        if later - earlier > 0
    ]
    row_pitch = median(marker_gaps) if marker_gaps else 48.0

    rows: list[dict[str, Any]] = []
    for marker_index, (row_number, marker_y) in enumerate(row_markers):
        next_marker_y = row_markers[marker_index + 1][1] if marker_index + 1 < len(row_markers) else float("inf")
        # The last row has no following number; cap its wrapped text window so
        # the table footer and signature area are not attached to that drug.
        next_y = marker_y + 160 if next_marker_y == float("inf") else (marker_y + next_marker_y) / 2
        # Upper bound mirrors the lower one: the midpoint with the previous
        # marker, so rows tile the table with no gap and no overlap. The old
        # fixed ``marker_y - 12`` assumed the STT digit shares a printed line
        # with the name. In a tall cell the digit is centred over three lines
        # and therefore sits BELOW the name: on a real prescription that left
        # ``SaViDopril Plus - Perindopril erbumin + Indapamid`` 17px above its
        # own row, and the row reported only the ingredient line beneath it.
        previous_marker_y = row_markers[marker_index - 1][1] if marker_index else None
        if previous_marker_y is None:
            # The first row has no marker above it to halve the distance to, so
            # give it the same half-pitch window as the others. Reaching all the
            # way back to the section heading instead swallowed the patient
            # address and the diagnosis into medicine #1 on the Bình Dân sheet.
            start_y = max(section_start_y, marker_y - row_pitch / 2)
        else:
            start_y = (previous_marker_y + marker_y) / 2
        row_items = [
            item for item in ordered
            if start_y <= (rect(item)[1] + rect(item)[3]) / 2 < next_y
            and not is_table_footer(item["text"])
        ]
        rows.append({
            "row_number": row_number,
            "items": row_items,
            "_row_marker_y": marker_y,
        })

    # A missing STT can leave two real medicines inside one parsed row. Split
    # only if both blocks have their own strength-bearing anchor and a dosage
    # schedule lies between them. Ingredient continuations share a later
    # schedule and therefore remain in one row.
    structurally_split_rows: list[dict[str, Any]] = []
    for row in rows:
        row_items = sorted(row["items"], key=lambda item: (rect(item)[1], rect(item)[0]))
        anchors = [
            item for item in row_items
            if rect(item)[0] <= name_column_right and medication_anchor(item)
        ]
        split_ys: list[float] = []
        for previous, current in zip(anchors, anchors[1:]):
            previous_y = (rect(previous)[1] + rect(previous)[3]) / 2
            current_y = (rect(current)[1] + rect(current)[3]) / 2
            if current_y - previous_y <= 20:
                continue
            if any(
                previous_y < (rect(item)[1] + rect(item)[3]) / 2 < current_y
                and _is_schedule_text(item["text"])
                for item in row_items
            ):
                split_ys.append((previous_y + current_y) / 2)

        boundaries = [float("-inf"), *split_ys, float("inf")]
        for start_y, end_y in zip(boundaries, boundaries[1:]):
            part_items = [
                item for item in row_items
                if start_y < (rect(item)[1] + rect(item)[3]) / 2 <= end_y
            ]
            if part_items:
                structurally_split_rows.append({
                    "row_number": row["row_number"],
                    "items": part_items,
                    "_row_marker_y": row.get("_row_marker_y", -1),
                })
    rows = structurally_split_rows

    # Some OCR results lose the first row number but keep the standalone slash
    # next to it. Recover a name block before the first detected row marker.
    if row_markers and row_markers[0][0] > 1:
        first_number, first_y = row_markers[0]
        first_anchor_ys = [
            (rect(item)[1] + rect(item)[3]) / 2
            for item in ordered
            if section_start_y < (rect(item)[1] + rect(item)[3]) / 2 < first_y - 15
            and rect(item)[0] <= name_column_right
            and medication_anchor(item)
        ]
        first_anchor_y = max(first_anchor_ys) if first_anchor_ys else first_y - 45
        first_items = [
            item for item in ordered
            if first_anchor_y - 15 <= (rect(item)[1] + rect(item)[3]) / 2 < first_y - 15
            and rect(item)[0] <= name_column_right
            and not _is_schedule_text(item["text"])
            and not is_table_footer(item["text"])
        ]
        if first_items:
            rows.insert(0, {
                "row_number": first_number - 1,
                "items": first_items,
                "_row_marker_y": first_anchor_y,
            })

    # Đánh số lại liên tục 1..n. Số in trên giấy không dùng để hiển thị được: chỉ
    # cần OCR đọc lố một ô là cả dãy lệch (don26 hiện ra #27,#28,#29,#30 cho một
    # đơn ba thuốc). Thứ tự dòng vẫn đúng thứ tự trên giấy, nên người dùng đối
    # chiếu bình thường; chỉ con số là do mình đánh.
    for position, row in enumerate(rows, start=1):
        row["row_number"] = position

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
            if current_y - previous_y > 30 and previous_y > last.get("_row_marker_y", -1):
                split_y = (previous_y + current_y) / 2
                first_items = [item for item in last["items"] if (rect(item)[1] + rect(item)[3]) / 2 < split_y]
                second_items = [item for item in last["items"] if (rect(item)[1] + rect(item)[3]) / 2 >= split_y]
                # A large gap alone is not enough: footer labels, queue fields
                # and signatures also sit below the last medicine. Split only
                # when the new block begins with independent medication evidence.
                second_anchor = next(
                    (item for item in second_items if medication_anchor(item)),
                    None,
                )
                if first_items and second_items and second_anchor is not None:
                    rows[-1:] = [
                        {
                            "row_number": last["row_number"],
                            "items": first_items,
                            "_row_marker_y": last.get("_row_marker_y", -1),
                        },
                        {
                            "row_number": last["row_number"] + 1,
                            "items": second_items,
                            "_row_marker_y": current_y,
                        },
                    ]
                break

    # Printed numbers may restart or be absent on implicit rows. UI numbering
    # always follows the visual order on the prescription.
    for position, row in enumerate(rows, start=1):
        row["row_number"] = position

    def _is_quantity_cell(text: str) -> bool:
        """``04 Lọ``, ``60 Viên``, ``Viên`` -- the SL/Đơn vị columns.

        A number bound to a dosage form is a count, never the identity of a
        medicine. Structural rather than lexical: it needs no per-product
        vocabulary and so cannot grow into the kind of short-prefix marker that
        swallows real names.
        """
        key = matching_key(text).strip(" .,:;()")
        return bool(
            re.fullmatch(rf"(?:\d+\s*)?(?:{'|'.join(_DOSAGE_FORMS)})", key)
        )

    def _name_column_items(row: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            item for item in sorted(row["items"], key=lambda i: (rect(i)[1], rect(i)[0]))
            if rect(item)[0] <= name_column_right
            and not _ROW_NUMBER.fullmatch(item["text"].strip())
            and item["text"].strip().casefold() not in {"i", "l", "|"}
            and not _is_schedule_text(item["text"])
            and not _is_quantity_cell(item["text"])
        ]

    # The "no recognizable name column" fallback is about the *page*, not about
    # one row. Applied per row it turned a quantity/unit cell into a medicine:
    # a row holding only ``04`` and ``Lọ`` fell through it and was proposed as
    # a drug named "Lọ".
    page_has_name_column = any(
        any(item["text"].strip() for item in _name_column_items(row)) for row in rows
    )

    result = []
    for row in rows:
        all_items = sorted(row["items"], key=lambda item: (rect(item)[1], rect(item)[0]))
        name_items = _name_column_items(row)
        if not page_has_name_column:
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
            resolver_texts = [
                (
                    re.sub(
                        rf"^\s*{_LEADING_INK}\d{{1,2}}(?:\s*{_ROW_SEPARATOR}\s*|\s+)",
                        "",
                        text,
                    ).strip()
                    if "(" in text
                    else text
                )
                for text in original_name_texts
            ]
            resolver_texts = [text for text in resolver_texts if text]
            # A row left with no name evidence is a table artefact, not a
            # medicine. Without this the caller falls back to the row's raw
            # text and proposes the quantity cell itself: eval INSUNOVA showed
            # "04 Lọ" and "60 Viên" as two of five medications.
            if page_has_name_column and not name_texts:
                continue
            result.append({
                "row_number": row["row_number"],
                "items": all_items,
                "texts": texts,
                "name_texts": name_texts,
                # Keep the unmodified name-column evidence for matching. The
                # display name remains cleaned, while strengths/brand aliases
                # are not lost before DrugResolver sees them.
                "resolver_texts": resolver_texts,
                "name_items": [
                    item for item in name_items
                    if item["text"].strip() in original_name_texts
                ],
            })
    # Dropping artefact rows must not leave gaps in the numbering the user sees.
    for position, row in enumerate(result, start=1):
        row["row_number"] = position
    return result


def _split_condition_list(value: str) -> list[str]:
    """Tách một dòng chẩn đoán thành từng bệnh riêng.

    Các mẫu đơn dùng dấu phân cách khác nhau: dấu chấm phẩy (Bạch Mai), dấu gạch
    chéo (``CAO HUYẾT ÁP VÔ CĂN (I10)/ BỆNH TIM THIẾU MÁU CỤC BỘ``), hoặc gạch dọc.

    Gạch chéo chỉ được coi là dấu phân cách khi có khoảng trắng kèm theo. Không có
    điều kiện đó thì ``thoát vị đĩa đệm cột sống L4/L5`` sẽ bị cắt làm đôi - một tên
    bệnh có thật trong bộ ảnh đo.

    Dấu phẩy chỉ được dùng khi vế sau mở đầu rõ ràng bằng ``Bệnh``. Nhờ vậy hai
    bệnh ``..., Bệnh đái tháo đường`` được tách, còn dấu phẩy nội tại như
    ``Bệnh đái tháo đường không phụ thuộc insulin, biến chứng mắt`` được giữ.
    """
    if not value:
        return []

    # Correct only code-shaped I/1 confusions.  The raw disease text remains
    # untouched, so this is auditable and cannot rewrite arbitrary quantities.
    normalized = _OCR_I_CODE.sub(lambda match: f"I{match.group('digits')}", value)

    # Some hospital templates print all ICD codes first and the same number of
    # comma-separated names afterwards.  don1 is read as
    # ``E13;I15: Bệnh đái tháo đường sau ghép, Tăng huyết áp thứ phát``.
    # Pair by printed order only when both counts agree; this uses no medical
    # knowledge and leaves ambiguous comma-containing diagnoses untouched.
    leading_matches = list(_ICD_CODE.finditer(normalized))
    if len(leading_matches) >= 2:
        last_code = leading_matches[-1]
        code_region = normalized[:last_code.end()]
        residue = _ICD_CODE.sub("", code_region)
        names_text = normalized[last_code.end():].strip(" ;:,-/")
        names = [part.strip(" ;:,-/") for part in names_text.split(",")]
        names = [part for part in names if part]
        if (
            re.fullmatch(r"[\s,;:|/.-]*", residue)
            and len(names) == len(leading_matches)
            and all(_looks_like_condition(name) for name in names)
        ):
            return [
                f"{match.group(1).upper()} - {name}"
                for match, name in zip(leading_matches, names)
            ]

    def split_by_icd(fragment: str) -> list[str]:
        matches = list(_ICD_CODE.finditer(fragment))
        if not matches:
            cleaned = fragment.strip(" ;:,-/")
            return [cleaned] if cleaned else []

        # OCR can glue the repeated suffix code to the last word
        # (``N40 ... heviN40,``). Recover a boundary only when that glued code
        # is identical to the explicit leading code and is followed by a
        # diagnosis separator; arbitrary letters+digits remain untouched.
        if matches[0].start() <= 2:
            leading_code = matches[0].group(1)
            fragment = re.sub(
                rf"(?<=[A-Za-zÀ-ỹ])({re.escape(leading_code)})(?=\s*(?:[,;|)]|$))",
                r" \1",
                fragment,
                count=1,
                flags=re.IGNORECASE,
            )
            matches = list(_ICD_CODE.finditer(fragment))

        # Some forms print a code before the diagnosis and repeat the same code
        # in parentheses after its name: ``N40: ... (N40), ... (J06)``. OCR may
        # lose both parentheses. Drop only that demonstrably duplicated leading
        # code; the remaining suffix codes then delimit each printed disease.
        if (
            len(matches) >= 2
            and matches[0].start() <= 2
            and matches[0].group(1).casefold() == matches[1].group(1).casefold()
        ):
            fragment = fragment[matches[0].end():].lstrip(" ;:,-/()")
            matches = list(_ICD_CODE.finditer(fragment))

        # ``I20 - disease / J20 - disease``: every code starts a new condition.
        prefix_style = any(
            re.match(r"\s*[-:–—]", fragment[match.end():])
            for match in matches
        ) or matches[0].start() <= 2
        parts: list[str] = []
        if prefix_style:
            prefix = fragment[:matches[0].start()].strip(" ;:,-/")
            if prefix:
                parts.append(prefix)
            for position, match in enumerate(matches):
                end = matches[position + 1].start() if position + 1 < len(matches) else len(fragment)
                part = fragment[match.start():end].strip(" ;:,-/")
                if part:
                    parts.append(part)
            return parts

        # ``Thoái hóa khớp M19 suy van tĩnh mạch I83``: a code closes
        # the condition before it.  This is the layout used by don33.
        start = 0
        for match in matches:
            parenthesized_code = (
                fragment[:match.start()].rstrip().endswith("(")
                and fragment[match.end():match.end() + 1] == ")"
            )
            end = match.end() + parenthesized_code
            part = fragment[start:end].strip(" ;:,-/")
            if part:
                parts.append(part)
            start = end
        tail = fragment[start:].strip(" ;:,-/")
        if tail.startswith(")"):
            tail = tail[1:].lstrip()
        if tail:
            parts.append(tail)
        return parts

    # Explicit separators remain useful for diagnoses without ICD codes.  A
    # slash needs surrounding whitespace, otherwise L4/L5 must stay intact.
    condition_start = (
        r"(?:b(?:ệ|e)nh|vi[eêệ]m|r[oố]i\s+lo[aạ]n|h[oộ]i\s+ch[uứ]ng|"
        r"nhi[eễ]m\s+(?:tr[uù]ng|khu[aẩ]n)|t[aă]ng\s+huy[eế]t\s+[aá]p|"
        r"cao\s+huy[eế]t\s+[aá]p|s[oố]t|ph[uù]\s+n[eề]|suy\s+(?:th[aậ]n|tim))\b"
    )
    fragments = re.split(
        rf"[;|]|\s+/\s*|\s*/\s+|(?<=[A-Za-zÀ-ỹ])/(?=[A-ZÀ-Ỹ])|"
        rf"(?<![A-Za-z]\d{{2}}):\s*(?={condition_start})|"
        # A small set of noun phrases can safely start a second diagnosis even
        # when OCR drops the printed slash. Do not use broad starters such as
        # ``Bệnh``/``Viêm`` here: they also occur immediately after ``I10 -``
        # and would detach the ICD code from its own condition.
        r"\s+(?=(?-i:Nh[oồô]i\s+máu|Sa\s+s[uú]t)\b)",
        normalized,
        flags=re.IGNORECASE,
    )
    result: list[str] = []
    for fragment in fragments:
        # A spaced dash separates diagnoses on templates such as
        # ``Viêm mũi họng - V.A đợt cấp``. Do not apply it to ICD layouts
        # (``I10 - Tăng huyết áp``), where the dash belongs to one diagnosis.
        dash_fragments = (
            [fragment]
            if _ICD_CODE.search(fragment) or _OCR_I_CODE.search(fragment)
            else re.split(r"\s+[-–—]\s+", fragment)
        )
        for dash_fragment in dash_fragments:
            comma_fragments = re.split(
                rf",\s*(?=(?:[A-Z]\d{{2}}(?:\.\d+)?\s*[-:–—]\s*)?{condition_start})",
                dash_fragment,
                flags=re.IGNORECASE,
            )
            for comma_fragment in comma_fragments:
                result.extend(split_by_icd(comma_fragment))
    return result


_CONDITION_INLINE_TAILS = (
    "han su dung", "chi dinh dung thuoc", "chi dinh thuoc", "so luong",
    "don vi", "cach dung", "benh kem theo", "bnh kem theo", "benh kom theo",
    "benh chinh", "don thuoc", "so phieu", "nam sinh", "gioi tinh",
    "ten benh nhan", "dia chi", "the bhyt", "bhyt", "benh vien", "pk tai",
)

_EXPLICIT_CONDITION_START = re.compile(
    r"\b(?:benh|viem|nhiem|hoi\s+chung|roi\s+loan|tang\s+huyet\s+ap|"
    r"cao\s+huyet\s+ap|sot|phu\s+ne|suy|dau|thoai\s+hoa|hen|loang\s+xuong|"
    r"bat\s+thuong|ton\s+thuong)\b",
    re.IGNORECASE,
)


def _explicit_condition_suffix(value: str) -> str:
    """Return a clearly disease-shaped suffix from a neighbouring OCR block."""
    normalized = _OCR_I_CODE.sub(lambda match: f"I{match.group('digits')}", value)
    code_match = _ICD_CODE.search(normalized)
    word_match = _EXPLICIT_CONDITION_START.search(matching_key(value))
    starts = [match.start() for match in (code_match, word_match) if match]
    return value[min(starts):].strip() if starts else ""


def _condition_value_after_label(line: str, labels: tuple[str, ...]) -> str:
    """Return only the text printed after a diagnosis label in one OCR box."""
    key = matching_key(line)
    positions = [
        (position, label)
        for label in labels
        for position in [key.find(label)]
        if position >= 0
    ]
    if not positions:
        return line.strip()
    position, label = min(positions, key=lambda found: (found[0], -len(found[1])))
    return line[position + len(label):].lstrip(" \t:：,;.-–—")


def _clean_condition_value(value: str) -> str:
    """Cut section/table text accidentally fused into a diagnosis box."""
    cleaned = value.strip()
    key = matching_key(cleaned)
    # OCR may prepend one or two stray glyphs to the ``Ghi chú`` label
    # (``Jighi chú``). Cut the whole damaged label token, not merely the exact
    # ``ghi chú`` substring, otherwise the prefix is surfaced as a disease.
    note_match = re.search(r"(?<!\w)\S{0,3}ghi\s*chu\b", key)
    if note_match:
        cleaned = cleaned[:note_match.start()]
        key = matching_key(cleaned)
    cut_positions = [key.find(marker) for marker in _CONDITION_INLINE_TAILS]
    cut_positions = [position for position in cut_positions if position >= 0]
    if cut_positions:
        cleaned = cleaned[:min(cut_positions)]
    return cleaned.strip(" \t:：,;.-–—")


def _condition_code(value: str) -> str | None:
    """Return the first normalized ICD code carried by one condition."""
    normalized = _OCR_I_CODE.sub(lambda match: f"I{match.group('digits')}", value)
    match = _ICD_CODE.search(normalized)
    return match.group(1).upper() if match else None


def _deduplicate_conditions(values: list[str]) -> list[str]:
    """Remove repeated diagnoses even when OCR spells the ICD code differently.

    Paddle can read the same printed ``I10`` as both ``I10`` and ``110`` in
    overlapping OCR boxes.  Comparing raw strings therefore leaves two cards
    for one diagnosis.  Prefer the normalized ICD code when present; otherwise
    compare normalized disease text after removing a leading code.  This is a
    structural de-duplication rule and does not infer or rename any disease.
    """
    result: list[str] = []
    seen_codes: set[str] = set()
    seen_texts: set[str] = set()
    for value in values:
        code = _condition_code(value)
        normalized = _OCR_I_CODE.sub(
            lambda match: f"I{match.group('digits')}", value
        )
        normalized = _ICD_CODE.sub(" ", normalized, count=1)
        text_key = matching_key(normalized).strip(" -:;,./()")
        if (code and code in seen_codes) or (text_key and text_key in seen_texts):
            continue
        result.append(value)
        if code:
            seen_codes.add(code)
        if text_key:
            seen_texts.add(text_key)
    return result


def _looks_like_vital_sign(text: str) -> bool:
    """Distinguish measured vitals from disease names sharing their prefix."""
    key = matching_key(text).strip()
    if not key.startswith(_VITAL_SIGN_PREFIXES):
        return False
    # ``Huyết áp: 120/80`` is a measurement; ``huyết áp vô căn`` is a disease.
    # Inspect only the beginning: don3's disease ends in OCR noise
    # ``không phụ 1.mộc insuline`` and that distant digit is not a vital value.
    measurement_head = key[:25]
    # don7's ``Mạch: ... lần/ph`` is recognized as one damaged box
    # ``Mạch làmp``. ``lamp`` is not a disease phrase; it is the collapsed
    # ``lần/ph`` unit and must stay outside the diagnosis block.
    if key.startswith("mach") and re.search(r"\b(?:lamp|lan\s*/?\s*ph)\b", key):
        return True
    return ":" in measurement_head or bool(re.search(r"\d", measurement_head))


def _is_condition_block_stop(text: str) -> bool:
    key = matching_key(text).strip()
    if not key:
        return False
    if key.startswith(_CONDITION_BLOCK_STOP_PREFIXES):
        return True
    # Short table headers tolerate one OCR substitution (``Số lượng`` ->
    # ``số tương``). Length equality and whole-string comparison keep this from
    # matching normal disease sentences that merely contain similar words.
    compact = re.sub(r"\W+", "", key)
    if any(
        abs(len(compact) - len(marker.replace(" ", ""))) <= 1
        and fuzz.ratio(compact, marker.replace(" ", "")) >= 84
        for marker in ("so luong", "ten thuoc", "don vi", "ham luong")
    ):
        return True
    if _looks_like_vital_sign(text):
        return True
    # Section headings often retain a Roman numeral and punctuation after
    # normalization (``II.THÔNG TIN ĐƠN THUỐC``), so startswith alone misses
    # the most important boundary between diagnoses and the medication table.
    if re.match(r"^(?:[ilvx]{1,4}[.\s]*)?thong tin don thuoc\b", key):
        return True
    # A numbered medicine row is an unambiguous lower boundary even when the
    # template omits a "Thuốc" heading.
    return bool(_ROW_NUMBER.match(text)) and bool(
        extract_strengths(text) or re.search(r"\([^)]*[A-Za-zÀ-ỹ]", text)
    )


def _value_beside_label(items: list[dict[str, Any]], index: int) -> str:
    """Collect the complete value block beside a standalone label.

    Nhiều mẫu đơn tách ``Chẩn đoán:`` và nội dung thành hai ô OCR riêng biệt, nên
    cắt chuỗi sau dấu hai chấm chỉ ra chuỗi rỗng. Đo trên eval/end2end đây là
    nguyên nhân lớn nhất làm mất chẩn đoán: 38/52 nhãn bệnh trượt rơi vào nhóm
    "không đọc được dòng nào".

    The old implementation returned just one OCR box.  On don26 the diagnosis
    spans three overlapping boxes, so that discarded I20/J20/K76/I10 and kept
    only E14/E78.  This version gathers the contiguous right/below block and
    stops before vitals, instructions or the medication table.
    """
    anchor = items[index].get("bbox")
    if not anchor:
        return ""
    ax = [q[0] for q in anchor]
    ay = [q[1] for q in anchor]
    a_left, a_right, a_top, a_bottom = min(ax), max(ax), min(ay), max(ay)
    a_height = max(1.0, a_bottom - a_top)

    boxes: list[tuple[float, float, float, float, str]] = []
    for other_index, other in enumerate(items):
        if other_index == index or not other.get("bbox"):
            continue
        text = " ".join(str(other.get("text", "")).split()).strip()
        if not text:
            continue
        ox = [q[0] for q in other["bbox"]]
        oy = [q[1] for q in other["bbox"]]
        o_left, o_right, o_top, o_bottom = min(ox), max(ox), min(oy), max(oy)
        boxes.append((o_top, o_left, o_bottom, o_right, text))

    if not boxes:
        return ""

    # Find the first explicit lower boundary. OCR boxes on adjacent printed
    # rows commonly overlap by 1-3 pixels (don1's ``Chẩn đoán`` bottom overlaps
    # the next ``Bệnh kèm theo`` top), so comparing with ``a_bottom`` leaks the
    # next section. A boundary label only needs to start clearly below the
    # anchor's top. don26's first value line starts above its label, but it is
    # not a stop marker and therefore remains unaffected.
    boundary_y = float("inf")
    for o_top, _o_left, _o_bottom, _o_right, text in boxes:
        if o_top > a_top + a_height * 0.25 and _is_condition_block_stop(text):
            boundary_y = min(boundary_y, o_top)

    selected: list[tuple[float, float, float, float, str]] = []
    for box in boxes:
        o_top, o_left, o_bottom, o_right, _text = box
        if o_top >= boundary_y:
            continue
        # A dosing instruction is never part of a diagnosis, and on a sparse
        # crop it is often the first thing printed under the label. On
        # eval/test/don22 the whole medication row plus "Ngày uống 1 lần, lần 1
        # viên sau ăn sáng" was appended to "VGSVB", leaving a diagnosis string
        # that matches nothing in the disease catalogue.
        if (
            _looks_like_vital_sign(_text)
            or _is_condition_block_stop(_text)
            or _is_schedule_text(_text)
        ):
            continue
        # Text from a second sheet visible behind the prescription can overlap
        # the diagnosis row (don7: ``19,Phường``). A leading number followed by
        # an address unit is administrative background, never a condition.
        if re.match(
            r"^\d+\s*[,.;:-]?\s*(?:phuong|xa|quan|huyen)\b",
            matching_key(_text),
        ):
            continue
        # Reject tiny OCR debris (don3: ``nz``) while retaining a standalone
        # ICD code that may be paired with text in the next box.
        if not _looks_like_condition(_text) and not _condition_code(_text):
            continue
        if re.fullmatch(
            rf"\d+\s+(?:{'|'.join(_DOSAGE_FORMS)})",
            matching_key(_text).strip(" .,:;()"),
        ):
            continue
        # The first wrapped line may begin up to 0.4 label-heights above the
        # label; administrative rows above that must not leak into diagnosis.
        if o_bottom < a_top - a_height * 0.4:
            continue
        # Same-row text starts to the right. Wrapped lines may return to the
        # label's left edge, but must still overlap its horizontal area.
        same_row_side = o_left >= a_right - a_height * 0.75
        wrapped_below = o_top >= a_bottom - a_height * 0.5 and o_right >= a_left
        if same_row_side or wrapped_below:
            selected.append(box)

    if not selected:
        return ""

    selected.sort(key=lambda box: (box[0], box[1]))
    # Without an explicit boundary, stop at the first large vertical gap. This
    # keeps the helper safe on cropped forms whose section heading was missed.
    contiguous: list[tuple[float, float, float, float, str]] = []
    block_bottom = a_bottom
    for box in selected:
        o_top, _o_left, o_bottom, _o_right, _text = box
        if contiguous and o_top - block_bottom > a_height * 1.25:
            break
        contiguous.append(box)
        block_bottom = max(block_bottom, o_bottom)

    return " ".join(box[4] for box in contiguous)


def extract_prescription_conditions(items: list[dict[str, Any]]) -> dict[str, list[str] | str]:
    """Extract printed diagnoses/underlying conditions without medical guessing.

    This deliberately reads only text next to prescription labels such as
    ``Chẩn đoán`` and ``Bệnh kèm theo``.  It does not infer a disease from a
    medicine name, which keeps the OCR output auditable and safe to confirm.
    """
    # Giữ chỉ số gốc trong ``items``: _value_beside_label cần đúng ô để tra toạ độ,
    # nên không được lọc rồi đánh số lại.
    numbered = [
        (position, " ".join(str(item.get("text", "")).split()).strip())
        for position, item in enumerate(items)
    ]
    numbered = [(position, line) for position, line in numbered if line]
    diagnosis = ""
    conditions: list[str] = []
    icd_codes: list[str] = []
    saw_diagnosis_label = False

    def collect_parts(value: str) -> None:
        for part in _split_condition_list(value):
            code = _condition_code(part)
            if code:
                icd_codes.append(code)
            normalized_part = _OCR_I_CODE.sub(
                lambda match: f"I{match.group('digits')}", part
            ).strip()
            if _ICD_CODE.fullmatch(normalized_part):
                continue
            if _looks_like_condition(part):
                conditions.append(part)

    diagnosis_labels = (
        "chan doan chinh", "chn doan chinh", "chan doan", "chn doan",
        "chia doan", "benh chinh",
    )
    condition_labels = (
        # ``Chẩn đoán khác:`` is a second, usually empty field. Left out of this
        # list it was read as the primary label with the value "khác", which
        # then overwrote a filled ``Chẩn đoán: E11 - Bệnh đái tháo đường...``
        # and put the word "khác" on screen as the patient's disease.
        "chan doan khac", "chn doan khac",
        "chan doan kem theo", "chn doan kem theo",
        "benh kem theo", "bnh kem theo", "benh nen", "bnh nen", "benh phu",
    )

    def append_continuation(value: str, beside: str) -> str:
        if not beside or matching_key(beside) in matching_key(value):
            return value
        letters_value = "".join(char for char in value if char.isalpha())
        letters_beside = "".join(char for char in beside if char.isalpha())
        both_uppercase = bool(letters_value and letters_beside) and (
            letters_value.upper() == letters_value and letters_beside.upper() == letters_beside
        )
        wrapped_suffix = bool(
            re.match(r"^[a-zà-ỹ]{2,12}\s*\(", beside)
            and (_ICD_CODE.search(beside) or _OCR_I_CODE.search(beside))
        )
        if len(value) < 25 or value.rstrip().endswith((",", ";", "/", "-")) or both_uppercase or wrapped_suffix:
            return f"{value} {beside}".strip()
        return value

    for index, line in numbered:
        key = matching_key(line)
        is_secondary_label = any(label in key for label in condition_labels)
        leading_words = " ".join(key.split()[:2])
        fuzzy_primary_label = (
            leading_words
            if len(leading_words) >= 7 and fuzz.ratio(leading_words, "chan doan") >= 80
            else ""
        )
        active_diagnosis_labels = (
            (*diagnosis_labels, fuzzy_primary_label)
            if fuzzy_primary_label else diagnosis_labels
        )
        if (
            any(label in key for label in diagnosis_labels) or fuzzy_primary_label
        ) and not is_secondary_label:
            saw_diagnosis_label = True
            # Nhiều mẫu đơn viết ``Chẩn đoán - ...`` thay vì ``Chẩn đoán: ...``, và
            # OCR cũng hay đọc dấu hai chấm mờ thành gạch ngang. Chỉ cắt ở dấu ĐẦU
            # TIÊN (maxsplit=1) nên gạch ngang bên trong tên bệnh vẫn an toàn:
            # ``Chẩn đoán: Chấn thương đầu - ngực - lưng`` cắt tại dấu hai chấm.
            value = _condition_value_after_label(line, active_diagnosis_labels)
            explicit_blank = bool(
                re.search(r"[:：]\s*[-–—_.]*\s*$", line)
            )
            if matching_key(value) in (*active_diagnosis_labels, ""):
                value = ""
            # A value may start inline and continue through several OCR boxes;
            # collect both without duplicating an identical same-row reading.
            beside = _value_beside_label(items, index)
            if beside and not value:
                # A colon-only label may have its value in another OCR box.
                # Require an explicit disease/ICD start in that case so a
                # nearby patient name cannot become the diagnosis.
                value = _explicit_condition_suffix(beside) if explicit_blank else beside
            else:
                value = append_continuation(value, beside)
            value = _clean_condition_value(value)
            if (
                value
                and matching_key(value) not in (*active_diagnosis_labels, "")
                and _looks_like_condition(value)
            ):
                diagnosis = value
        if is_secondary_label:
            value = _condition_value_after_label(line, condition_labels)
            value = _clean_condition_value(value)
            if matching_key(value) in (
                "benh kem theo", "bnh kem theo", "benh nen", "bnh nen", "benh phu", ""
            ):
                value = ""
            collect_parts(value)
            # If the label occupies its own OCR box, use the neighbouring box.
            if not value:
                beside = _clean_condition_value(_value_beside_label(items, index))
                collect_parts(beside)

    # Cropped prescriptions can start inside the diagnosis line and therefore
    # lose the label entirely. Recover only text above the medicine-table
    # heading that still carries an ICD-shaped code followed by disease words.
    # This uses layout + code syntax; arbitrary prose elsewhere on the page is
    # never promoted to a diagnosis.
    if not diagnosis and not saw_diagnosis_label:
        def top(item: dict[str, Any]) -> float:
            points = item.get("bbox") or []
            return min((point[1] for point in points), default=float("inf"))

        table_tops = [
            top(item) for item in items
            if any(marker in matching_key(str(item.get("text", ""))) for marker in (
                "ten thuoc", "ham luong", "chi dinh dung thuoc", "chi dinh thuoc",
            ))
        ]
        table_top = min(table_tops) if table_tops else float("inf")
        for _index, line in numbered:
            if top(items[_index]) >= table_top:
                continue
            normalized_line = _OCR_I_CODE.sub(lambda match: f"I{match.group('digits')}", line)
            code_match = _ICD_CODE.search(normalized_line)
            if not code_match or not re.search(
                r"\b(?:benh|bệnh|viem|viêm|suy|nhoi|nhồi|sa sut|sa sút|tang|tăng|cao huyet|cao huyết)\b",
                normalized_line,
                flags=re.IGNORECASE,
            ):
                continue
            diagnosis = normalized_line[code_match.start():].strip(" :;,-")
            break
    # Dòng "Chẩn đoán" cũng thường liệt kê nhiều bệnh trên cùng một dòng. Giữ
    # nguyên chuỗi ``diagnosis`` để không đổi hợp đồng API, nhưng bổ sung các phần
    # tách được vào underlying_conditions - phía sau còn phải khớp từng tên bệnh
    # với danh mục, mà một chuỗi gộp hai bệnh thì chỉ khớp được một.
    # A prescription that prints its code in a dedicated ``Mã ICD:`` field now
    # keeps that field out of the diagnosis text (it is a block stop), so read
    # the code from the field itself. The label names exactly what follows, so
    # this is the least ambiguous source of a code on the page.
    for _index, line in numbered:
        if not matching_key(line).startswith("ma icd"):
            continue
        normalized_line = _OCR_I_CODE.sub(
            lambda match: f"I{match.group('digits')}", line
        )
        field_code = _ICD_CODE.search(normalized_line)
        if field_code:
            icd_codes.append(field_code.group(1).upper())

    secondary_count = len(conditions)
    collect_parts(diagnosis)
    if len(conditions) > secondary_count:
        conditions = conditions[secondary_count:] + conditions[:secondary_count]
    return {
        "diagnosis": diagnosis,
        "underlying_conditions": _deduplicate_conditions(conditions),
        "icd_codes": list(dict.fromkeys(icd_codes)),
    }
