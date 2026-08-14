"use client";

import { useEffect, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import type { ProductSearchResult } from "@/lib/api";
import type { SelectedDrug } from "@/lib/prescription";

type PrescriptionPanelProps = {
  label: string;
  drugs: SelectedDrug[];
  search: (query: string) => Promise<ProductSearchResult[]>;
  onAdd: (name: string, known?: boolean) => void;
  onRemoveDrug: (name: string) => void;
  onRemovePanel?: () => void;
  onImport?: () => void;
  inputId: string;
};

export default function PrescriptionPanel({ label, drugs, search, onAdd, onRemoveDrug, onRemovePanel, onImport, inputId }: PrescriptionPanelProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);

  useEffect(() => {
    if (query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => search(query.trim()).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  function add(name: string, known = true) {
    onAdd(name, known);
    setQuery("");
    setSuggestions([]);
  }

  return (
    <div className="prescription-panel panel">
      <div className="prescription-panel__header">
        <h3>{label}</h3>
        {onRemovePanel && (
          <button type="button" className="prescription-panel__remove" onClick={onRemovePanel} aria-label={`Xóa ${label}`}>
            <MaterialIcon name="close" size={18} />
          </button>
        )}
      </div>
      <div className="prescription-panel__actions">
        {onImport && (
          <button type="button" className="prescription-panel__tool" onClick={onImport} title="Nhập từ hồ sơ thuốc đang dùng">
            <MaterialIcon name="download" size={16} /><span>Nhập từ hồ sơ</span>
          </button>
        )}
        <button type="button" className="prescription-panel__tool" disabled title="Quét đơn thuốc bằng OCR — tính năng sắp ra mắt">
          <MaterialIcon name="photo_camera" size={16} /><span>Quét OCR</span>
        </button>
      </div>

      <div className="interaction-search__input">
        <MaterialIcon name="search" size={19} />
        <input
          id={inputId}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Nhập tên thuốc, ví dụ Panadol"
          autoComplete="off"
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            if (suggestions[0]) add(suggestions[0].ten_thuoc);
            else if (query.trim()) add(query.trim(), false);
          }}
        />
        {query && (
          <button type="button" onClick={() => { setQuery(""); setSuggestions([]); }} aria-label="Xóa tìm kiếm">
            <MaterialIcon name="close" size={16} />
          </button>
        )}
      </div>
      {suggestions.length > 0 ? (
        <ul className="interaction-suggestions interaction-suggestions--inline">
          {suggestions.slice(0, 5).map((item) => (
            <li key={item.id} onClick={() => add(item.ten_thuoc)}>
              <div><strong>{item.ten_thuoc}</strong><small>Thuốc trong cơ sở dữ liệu</small></div>
              <MaterialIcon name="add_circle_outline" size={19} />
            </li>
          ))}
        </ul>
      ) : query.trim().length >= 2 && (
        <button type="button" className="interaction-unknown" onClick={() => add(query.trim(), false)}>
          <div><strong>Không tìm thấy "{query.trim()}"</strong><small>Thêm thuốc chưa cập nhật trong cơ sở dữ liệu</small></div>
          <MaterialIcon name="add_circle_outline" size={19} />
        </button>
      )}

      <div className="prescription-panel__list">
        {drugs.length === 0 && <p className="prescription-panel__empty">Chưa có thuốc nào trong đơn này.</p>}
        {drugs.map((item) => (
          <div className={`selected-medication ${!item.known ? "selected-medication--unknown" : ""}`} key={item.name}>
            <span className="selected-medication__icon"><MaterialIcon name="medication" size={18} /></span>
            <div><strong>{item.name}</strong><small>{item.known ? "Thuốc trong cơ sở dữ liệu" : "Chưa cập nhật trong cơ sở dữ liệu"}</small></div>
            <button type="button" onClick={() => onRemoveDrug(item.name)} aria-label={`Xóa ${item.name}`}><MaterialIcon name="close" size={17} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
