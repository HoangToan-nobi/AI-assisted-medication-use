from __future__ import annotations

from typing import TypedDict


class MedCheckState(TypedDict, total=False):
    """State schema cho LangGraph agent kiểm tra tương tác thuốc.

    Mỗi node đọc và ghi vào state này.
    total=False cho phép tất cả fields là optional.
    """

    raw_medications: list[str]
    normalized_medications: list[dict]
    interaction_results: list[dict]
    ranked_results: list[dict]
    explanations: list[dict]
    has_severe: bool
    has_unclassified: bool
    error: str
    metadata: dict
