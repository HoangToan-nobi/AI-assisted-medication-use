"use client";

import { useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import type { Severity } from "@/lib/api";

type AlertCardProps = {
  thuocA?: string;
  thuocB?: string;
  severity?: Severity;
  description: string;
  source: string;
  management?: string;
  // Bản dịch nguyên văn (không qua AI diễn giải lại, chỉ dịch sát nghĩa Anh -> Việt)
  // của mô tả khoa học từ CSDL DDInter 2.0 - chỉ backend trả về cho dược sĩ, bệnh
  // nhân không có field này nên luôn undefined.
  scientificDescription?: string;
};

const CONFIG: Record<Severity, { label: string; tag: string; icon: string; className: string }> = {
  nang: { label: "Nghiêm trọng", tag: "Nguy hiểm", icon: "dangerous", className: "severity-nang" },
  trung_binh: { label: "Trung bình", tag: "Cần lưu ý", icon: "warning", className: "severity-trung-binh" },
  nhe: { label: "Nhẹ", tag: "Theo dõi", icon: "info", className: "severity-nhe" },
  chua_phan_loai: { label: "Chưa phân loại", tag: "Chưa rõ", icon: "help", className: "severity-chua-phan-loai" },
};

export default function AlertCard({ thuocA, thuocB, severity, description, source, management, scientificDescription }: AlertCardProps) {
  const [sourceOpen, setSourceOpen] = useState(false);
  const config = severity ? CONFIG[severity] : { label: "Không đủ dữ liệu", tag: "Chưa cập nhật", icon: "block", className: "severity-none" };
  return <article className={`alert-card ${config.className}`} data-severity={severity ?? "none"}>
    <div className="alert-card-header"><span className="alert-icon-wrap"><MaterialIcon name={config.icon} size={22} filled /></span><div className="alert-card-body"><span className="alert-severity-tag">{config.tag}</span><h3>{thuocA && thuocB ? `${config.label}: ${thuocA} + ${thuocB}` : config.label}</h3></div></div>
    <p className="alert-description">{description}</p>
    {scientificDescription && <div className="alert-science-box"><strong>Mô tả khoa học (dịch nguyên văn từ CSDL DDInter 2.0)</strong>{scientificDescription}</div>}
    {management && <div className="alert-action-box"><strong>Khuyến nghị xử trí (dịch nguyên văn từ CSDL DDInter 2.0)</strong>{management}</div>}
    <div className={`citation-wrap ${sourceOpen ? "citation-wrap--open" : ""}`}><button type="button" className="citation-trigger" aria-expanded={sourceOpen} aria-label={`Xem nguồn: ${source}`} onClick={() => setSourceOpen((open) => !open)}><MaterialIcon name="database" size={15} /> <span className="citation-trigger__text">{source || "Nguồn trích dẫn"}</span><MaterialIcon name={sourceOpen ? "expand_less" : "expand_more"} size={16} /></button><div className="citation-popover" role="tooltip"><span className="citation-popover__label">NGUỒN THAM KHẢO</span><strong>{source || "Chưa có thông tin nguồn"}</strong><p>Nhấn lại nút nguồn để thu gọn thông tin tham khảo.</p></div></div>
  </article>;
}
