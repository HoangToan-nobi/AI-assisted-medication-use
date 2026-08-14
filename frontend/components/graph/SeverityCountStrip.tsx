import type { Severity } from "@/lib/api";

const CONFIG: { key: Severity; label: string; dotClass: string }[] = [
  { key: "nang", label: "Nghiêm trọng", dotClass: "tt-legend-dot--severe" },
  { key: "trung_binh", label: "Trung bình", dotClass: "tt-legend-dot--moderate" },
  { key: "nhe", label: "Nhẹ", dotClass: "tt-legend-dot--mild" },
  { key: "chua_phan_loai", label: "Chưa phân loại", dotClass: "tt-legend-dot--unknown" },
];

type SeverityCountStripProps = { edges: { muc_do?: Severity }[] };

export default function SeverityCountStrip({ edges }: SeverityCountStripProps) {
  const counts: Record<Severity, number> = { nang: 0, trung_binh: 0, nhe: 0, chua_phan_loai: 0 };
  for (const edge of edges) if (edge.muc_do) counts[edge.muc_do] += 1;

  return (
    <div className="tt-severity-strip">
      {CONFIG.map((c) => (
        <span key={c.key} className="tt-severity-strip__item">
          <i className={`tt-legend-dot ${c.dotClass}`} /> {c.label}: <strong>{counts[c.key]}</strong>
        </span>
      ))}
    </div>
  );
}
