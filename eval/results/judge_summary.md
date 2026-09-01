# Judge summary (metric 1, 4, 5, 6)

## faithfulness  ·  n=20 (parse OK 20)
- **mean_faithfulness: 0.7385**
- fail: 6 — ['dd-nang-001', 'dd-nhe-035', 'dis-trung_binh-018', 'food-nang-005', 'rt-label-010', 'rt-xutri-003']
- with_hallucination: 6 — ['dd-nang-001', 'dd-nhe-035', 'dis-trung_binh-018', 'food-nang-005', 'rt-label-010', 'rt-xutri-003']
- with_fabricated_numbers: 0 — []
- with_management_leak: 0 — []

## relevance  ·  n=19 (parse OK 19)
- **mean_score: 4.0**
- entity_leak: 2 — ['dd-nhe-035', 'food-nang-005']
- below_4: 4 — ['dd-nang-016', 'dd-trung_binh-027', 'food-nang-007', 'rt-xutri-003']

## completeness  ·  n=16 (parse OK 16)
- **mean_score: 0.844**
- missing_mechanism: 2 — ['dd-nang-016', 'food-nang-007']
- missing_consequence: 3 — ['dd-nang-016', 'dd-trung_binh-027', 'food-nang-007']

## consistency  ·  n=20 (parse OK 20)
- **clinically_equivalent_rate: 0.9**
- with_claim_flips: 2 — ['dis-nang-007', 'food-nang-007']
- safety_property_changed: 4 — ['dd-nhe-037', 'dd-trung_binh-021', 'dis-nang-007', 'food-trung_binh-015']
