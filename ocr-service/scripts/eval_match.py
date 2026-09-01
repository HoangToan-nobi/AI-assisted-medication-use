"""Measure drug-matching accuracy against ground truth.

`scripts/eval_ocr.py` scores what the recognizers read. This scores what the
resolver does with it: given the OCR text of one medication row, does the
right database row come back first?

The two are deliberately separate. OCR errors and ranking errors have
different fixes, and a single end-to-end number hides which one moved.

Usage:
    python scripts/eval_match.py                  # eval/drug_match.csv
    python scripts/eval_match.py --top 3          # count a hit anywhere in top 3
    python scripts/eval_match.py --verbose        # show every row

Ground truth lives in `eval/drug_match.csv` with columns
``source,ocr_line,expected``. Use ``__NOT_IN_DB__`` as the expected value for a
drug that is genuinely absent from the database: the service is correct there
only when it declines to assert a match, so those rows are scored on
`status`/`database_matches` rather than on the name.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.drug_resolver import DrugResolver  # noqa: E402
from app.utils.text_utils import matching_key  # noqa: E402

NOT_IN_DB = "__NOT_IN_DB__"
DEFAULT_SET = Path(__file__).resolve().parents[1] / "eval" / "drug_match.csv"


def classify(expected: str, candidates: list[dict], top: int, threshold: float) -> tuple[str, str]:
    """Return ``(outcome, detail)`` for one row."""
    best = candidates[0] if candidates else None
    got = best["drug_name"] if best else "—"

    if expected == NOT_IN_DB:
        # Correct behaviour is a refusal, not a name. A confident answer for a
        # drug that is not in the database is the worst outcome available: it
        # proposes a medicine the patient was never prescribed.
        if best is None or best["score"] < threshold:
            return "refused", f"{got} ({best['score']:.2f})" if best else "—"
        return "false_match", f"{got} ({best['score']:.2f})"

    wanted = matching_key(expected)
    names = [matching_key(c["drug_name"]) for c in candidates[:top]]
    if names and names[0] == wanted:
        return "hit", got
    if wanted in names:
        return f"top{top}", f"{got}  (đúng ở hạng {names.index(wanted) + 1})"
    return "miss", f"{got} ({best['score']:.2f})" if best else "—"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_SET)
    parser.add_argument("--top", type=int, default=3, help="Rank still counted as recovered")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Score below which a match counts as refused (default: DRUG_MEDIUM_CONFIDENCE)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.dataset.is_file():
        raise SystemExit(f"No ground truth at {args.dataset}")

    resolver = DrugResolver()
    resolver.load()
    threshold = (
        args.threshold if args.threshold is not None else resolver.settings.drug_medium_confidence
    )

    rows = list(csv.DictReader(args.dataset.open(encoding="utf-8")))
    counts: dict[str, int] = {}
    for row in rows:
        candidates = resolver.resolve([row["ocr_line"]])["candidates"]
        outcome, detail = classify(row["expected"], candidates, args.top, threshold)
        counts[outcome] = counts.get(outcome, 0) + 1
        if args.verbose or outcome in {"miss", "false_match"}:
            mark = {"hit": "✓", "refused": "✓", "miss": "✗", "false_match": "✗✗"}.get(outcome, "~")
            print(f"  {mark} [{row['source']}] {row['ocr_line'][:46]}")
            print(f"       mong đợi: {row['expected']}")
            print(f"       nhận được: {detail}")

    resolvable = [r for r in rows if r["expected"] != NOT_IN_DB]
    absent = len(rows) - len(resolvable)
    hits = counts.get("hit", 0)
    recovered = counts.get(f"top{args.top}", 0)
    print(f"\n{len(rows)} dòng ({len(resolvable)} có trong CSDL, {absent} không có)")
    print(f"  đúng ở hạng 1        {hits}/{len(resolvable)}"
          + (f"  ({hits / len(resolvable):.0%})" if resolvable else ""))
    print(f"  đúng trong top-{args.top}      {hits + recovered}/{len(resolvable)}")
    print(f"  trượt hẳn            {counts.get('miss', 0)}/{len(resolvable)}")
    if absent:
        print(f"  từ chối đúng         {counts.get('refused', 0)}/{absent}")
        print(f"  KHẲNG ĐỊNH SAI       {counts.get('false_match', 0)}/{absent}  (nguy hiểm nhất)")


if __name__ == "__main__":
    main()
