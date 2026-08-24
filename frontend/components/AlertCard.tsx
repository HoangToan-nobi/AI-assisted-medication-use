"use client";

import { useState } from "react";
import ExpandableText from "@/components/ExpandableText";
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
  // Trích dẫn ngắn gọn (1-2 câu/cặp hoạt chất góp phần) hiện trong popover nguồn -
  // rỗng/undefined thì popover rơi về hint mặc định.
  references?: string[];
};

const CONFIG: Record<Severity, { label: string; tag: string; icon: string; className: string }> = {
  nang: { label: "Nghiêm trọng", tag: "Nguy hiểm", icon: "dangerous", className: "severity-nang" },
  trung_binh: { label: "Trung bình", tag: "Cần lưu ý", icon: "warning", className: "severity-trung-binh" },
  nhe: { label: "Nhẹ", tag: "Theo dõi", icon: "info", className: "severity-nhe" },
  chua_phan_loai: { label: "Chưa phân loại", tag: "Chưa rõ", icon: "help", className: "severity-chua-phan-loai" },
};

// Thẻ luôn hiện đầy đủ giai_thich (rút gọn bằng ExpandableText nếu quá dài, xem
// component đó) - không còn thu-gọn-chỉ-header/bấm-để-mở-cả-thẻ như trước, vì
// bệnh nhân/dược sĩ cần đọc được cảnh báo ngay mà không phải bấm thêm 1 bước.
export default function AlertCard({ thuocA, thuocB, severity, description, source, management, scientificDescription, references }: AlertCardProps) {
  const [sourceOpen, setSourceOpen] = useState(false);
  // Dữ liệu gốc + xử trí gốc chỉ dược sĩ mới nhận được (bệnh nhân luôn undefined,
  // backend đã tự ẩn) - 2 nút bật/tắt độc lập (không còn loại trừ nhau) để dược sĩ
  // có thể mở cả 2 khối cùng lúc, xem tuần tự mô tả rồi tới xử trí.
  const [scienceOpen, setScienceOpen] = useState(false);
  const [managementOpen, setManagementOpen] = useState(false);
  const config = severity ? CONFIG[severity] : { label: "Không đủ dữ liệu", tag: "Chưa cập nhật", icon: "block", className: "severity-none" };
  return <article className={`alert-card ${config.className}`} data-severity={severity ?? "none"}>
    <div className="alert-card-header">
      <span className="alert-icon-wrap"><MaterialIcon name={config.icon} size={22} filled /></span>
      <div className="alert-card-body"><span className="alert-severity-tag">{config.tag}</span><h3>{thuocA && thuocB ? `${config.label}: ${thuocA} + ${thuocB}` : config.label}</h3></div>
    </div>
    <p className="alert-description"><ExpandableText text={description} /></p>
    {(scientificDescription || management) && (
      <div className="alert-detail-tabs">
        <div className="profile-tabs alert-detail-tabs__nav">
          {scientificDescription && (
            <button type="button" className={`profile-tabs__item ${scienceOpen ? "profile-tabs__item--active" : ""}`} aria-expanded={scienceOpen} onClick={() => setScienceOpen((open) => !open)}>
              <MaterialIcon name="science" size={15} /> Dữ liệu tương tác gốc
            </button>
          )}
          {management && (
            <button type="button" className={`profile-tabs__item ${managementOpen ? "profile-tabs__item--active" : ""}`} aria-expanded={managementOpen} onClick={() => setManagementOpen((open) => !open)}>
              <MaterialIcon name="medical_information" size={15} /> Cách xử lý gốc
            </button>
          )}
        </div>
        {scientificDescription && (
          <div className={`alert-detail-box__collapse ${scienceOpen ? "alert-detail-box__collapse--open" : ""}`}>
            <div className="alert-science-box"><strong>Mô tả khoa học (dịch nguyên văn từ CSDL DDInter 2.0)</strong><span>{scientificDescription}</span></div>
          </div>
        )}
        {management && (
          <div className={`alert-detail-box__collapse ${managementOpen ? "alert-detail-box__collapse--open" : ""}`}>
            <div className="alert-action-box"><strong>Khuyến nghị xử trí (dịch nguyên văn từ CSDL DDInter 2.0)</strong><span>{management}</span></div>
          </div>
        )}
      </div>
    )}
    <div className={`citation-wrap ${sourceOpen ? "citation-wrap--open" : ""}`}><button type="button" className="citation-trigger" aria-expanded={sourceOpen} aria-label={`Xem nguồn: ${source}`} onClick={() => setSourceOpen((open) => !open)}><MaterialIcon name="database" size={15} /> <span className="citation-trigger__text">{source || "Nguồn trích dẫn"}</span><MaterialIcon name={sourceOpen ? "expand_less" : "expand_more"} size={16} /></button><div className="citation-popover" role="tooltip"><span className="citation-popover__label">NGUỒN THAM KHẢO</span><strong>{source || "Chưa có thông tin nguồn"}</strong>{references?.length ? <ul className="citation-popover__refs">{references.map((ref, i) => <li key={i}>{ref}</li>)}</ul> : <p>Nhấn lại nút nguồn để thu gọn thông tin tham khảo.</p>}</div></div>
  </article>;
}
