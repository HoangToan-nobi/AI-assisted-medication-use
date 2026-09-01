import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

from src.db.models import Disease

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_GENERIC_PREFIXES = ("benh ly nen ", "benh nen ", "benh ly ", "benh ")

# Nhóm thuật ngữ y khoa tương đương, độc lập với disease_id. Đây là lớp từ vựng
# bổ sung cho tên chính thức trong CSDL; thuật toán tìm kiếm bên dưới vẫn chạy trên
# mọi Disease, kể cả bệnh không có mặt trong các nhóm này.
_EQUIVALENT_TERMS = (
    frozenset(("tieu duong", "dai thao duong", "diabetes", "diabetes mellitus")),
    frozenset(("cao huyet ap", "tang huyet ap", "hypertension")),
    frozenset(("hen suyen", "hen phe quan", "asthma")),
    frozenset(("dot quy", "tai bien mach mau nao", "stroke")),
)


def normalize_disease_search_text(value: str) -> str:
    """Chuẩn hóa chuỗi để so khớp tên bệnh có/không dấu một cách ổn định."""
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return _NON_ALPHANUMERIC.sub(" ", without_marks).strip()


def _without_generic_prefix(value: str) -> str:
    for prefix in _GENERIC_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def _query_variants(query: str) -> set[str]:
    normalized = normalize_disease_search_text(query)
    core = _without_generic_prefix(normalized)
    variants = {value for value in (normalized, core) if value}
    for group in _EQUIVALENT_TERMS:
        is_equivalent = core in group or (
            len(core) >= 5
            and any(SequenceMatcher(None, core, term).ratio() >= 0.9 for term in group)
        )
        if is_equivalent:
            variants.update(group)
    return variants


def _name_variants(disease: Disease) -> set[str]:
    variants: set[str] = set()
    for name in (disease.ten_benh_vi, disease.ten_benh):
        if not name:
            continue
        normalized = normalize_disease_search_text(name)
        if normalized:
            variants.add(normalized)
            variants.add(_without_generic_prefix(normalized))
    return variants


def _match_score(query: str, candidate: str) -> float:
    if query == candidate:
        return 1.0
    if candidate.startswith(query):
        return 0.96
    if query in candidate:
        return 0.9

    query_tokens = query.split()
    candidate_tokens = set(candidate.split())
    if len(query_tokens) > 1 and all(token in candidate_tokens for token in query_tokens):
        return 0.86

    # Không fuzzy-match từ quá ngắn vì dễ trả về bệnh không liên quan. Với chuỗi
    # dài, ngưỡng 0.84 đủ nhận typo nhẹ như "đái tháo đườn" nhưng vẫn chặt.
    if len(query) < 5:
        return 0.0
    ratio = SequenceMatcher(None, query, candidate).ratio()
    threshold = 0.84 if len(query) >= 8 else 0.9
    return ratio if ratio >= threshold else 0.0


def rank_disease_matches(
    diseases: Iterable[Disease], query: str, limit: int
) -> list[Disease]:
    """Lọc và xếp hạng bệnh theo tên Việt, tên Anh, bí danh và typo nhẹ."""
    query_variants = _query_variants(query)
    if not query_variants:
        return []

    ranked: list[tuple[float, str, Disease]] = []
    for disease in diseases:
        score = max(
            (
                _match_score(query_variant, name_variant)
                for query_variant in query_variants
                for name_variant in _name_variants(disease)
            ),
            default=0.0,
        )
        if score <= 0:
            continue
        display_name = disease.ten_benh_vi or disease.ten_benh
        ranked.append((-score, normalize_disease_search_text(display_name), disease))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].id))
    return [item[2] for item in ranked[:limit]]


# Độ dài tối thiểu của tên bệnh để được coi là "xuất hiện trong câu". Dưới ngưỡng
# này (VD "ho", "sốt") chuỗi con dễ trúng ngẫu nhiên giữa một từ khác.
_MIN_CONTAINED_NAME_LENGTH = 6


def _search_terms(disease: Disease) -> set[str]:
    """Tên bệnh cùng các cách gọi tương đương cần dò trong câu chẩn đoán."""
    terms = set(_name_variants(disease))
    for variant in list(terms):
        for group in _EQUIVALENT_TERMS:
            if variant in group:
                terms.update(group)
    return {term for term in terms if len(term) >= _MIN_CONTAINED_NAME_LENGTH}


def match_diseases_in_phrase(
    diseases: Iterable[Disease], phrase: str, limit: int
) -> list[Disease]:
    """Tìm bệnh trong danh mục có tên nằm BÊN TRONG một câu chẩn đoán.

    Ngược chiều với :func:`rank_disease_matches`, vốn phục vụ ô tìm kiếm: ở đó
    người dùng gõ vài chữ và hệ thống tìm tên đầy đủ, nên nó tính điểm theo
    "query nằm trong tên bệnh". Chẩn đoán in trên đơn thì đi kèm ngữ cảnh -
    ``Bệnh tăng huyết áp vô căn (nguyên phát)`` - nên quan hệ bị đảo lại: tên
    trong danh mục (``Tăng huyết áp``) là chuỗi con của câu, và ``_match_score``
    trả 0 cho mọi dòng như vậy.

    Tên khớp dài hơn được xếp trước, để ``Đái tháo đường týp 2`` thắng
    ``Đái tháo đường`` khi câu chẩn đoán nêu rõ týp. Không khớp được gì thì lùi
    về :func:`rank_disease_matches` cho các dòng đã vốn ngắn gọn.
    """
    normalized_phrase = normalize_disease_search_text(phrase)
    if not normalized_phrase:
        return []
    # OCR thường xoá mất dấu cách giữa các âm tiết ("tang huyet ap" -> "tang huyetap").
    # So thêm một lần trên bản đã bỏ hết dấu cách ở cả hai phía để những dòng đó
    # không trượt; khớp có dấu cách vẫn được ưu tiên vì tính điểm theo độ dài thật.
    squashed_phrase = normalized_phrase.replace(" ", "")

    contained: list[tuple[int, str, Disease]] = []
    for disease in diseases:
        matched = [
            term
            for term in _search_terms(disease)
            if term in normalized_phrase or term.replace(" ", "") in squashed_phrase
        ]
        if not matched:
            continue
        display_name = disease.ten_benh_vi or disease.ten_benh
        contained.append(
            (-max(len(term) for term in matched), normalize_disease_search_text(display_name), disease)
        )

    if not contained:
        return rank_disease_matches(diseases, phrase, limit)

    contained.sort(key=lambda item: (item[0], item[1], item[2].id))
    return [item[2] for item in contained[:limit]]
