import type { Severity } from "@/lib/api";

type AlertCardProps = {
  thuocA?: string;
  thuocB?: string;
  severity?: Severity;
  description: string;
  source: string;
  // Xử trí (DDInter Management) - CHỈ truyền prop này ở màn hình dược sĩ.
  management?: string;
};

const SEVERITY_CONFIG: Record<Severity, { label: string; icon: string; className: string }> = {
  nang: { label: "Nghiêm trọng", icon: "🔴", className: "severity-nang" },
  trung_binh: { label: "Trung bình", icon: "🟠", className: "severity-trung-binh" },
  nhe: { label: "Nhẹ", icon: "🟡", className: "severity-nhe" },
  chua_phan_loai: { label: "Chưa phân loại", icon: "⚪", className: "severity-chua-phan-loai" },
};

const NO_DATA_CONFIG = { label: "Không đủ dữ liệu", icon: "⚫", className: "severity-none" };

// Component chuẩn dùng lại cho cả bệnh nhân và dược sĩ (xem GĐ3 mục "Component chuẩn").
// Không dùng màu đơn thuần để truyền tải mức độ - luôn kèm icon + chữ mô tả.
export default function AlertCard({
  thuocA,
  thuocB,
  severity,
  description,
  source,
  management,
}: AlertCardProps) {
  const config = severity ? SEVERITY_CONFIG[severity] : NO_DATA_CONFIG;

  return (
    <div className={`alert-card ${config.className}`} data-severity={severity ?? "none"}>
      <div className="alert-card-header">
        <span className="alert-icon" aria-hidden="true">
          {config.icon}
        </span>
        <span className="alert-severity-label">{config.label}</span>
        {(thuocA || thuocB) && (
          <span className="alert-drug-pair">
            {thuocA} + {thuocB}
          </span>
        )}
      </div>
      <p className="alert-description">{description}</p>
      {management && (
        <p className="alert-management">
          <strong>Xử trí (chỉ dược sĩ xem):</strong> {management}
        </p>
      )}
      <p className="alert-source">Nguồn: {source}</p>
    </div>
  );
}
