"use client";

import { useEffect, useRef, useState } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import MediFox from "@/components/MediFox";
import PrescriptionScanModal from "@/components/PrescriptionScanModal";
import { ApiError, scanPrescription, type PatientPrescription, type ProductSearchResult, type ScanPrescriptionResponse } from "@/lib/api";
import type { SelectedDrug } from "@/lib/prescription";

type PrescriptionPanelProps = {
  label: string;
  drugs: SelectedDrug[];
  search: (query: string) => Promise<ProductSearchResult[]>;
  onAdd: (name: string, known?: boolean) => void;
  onRemoveDrug: (name: string) => void;
  onRemovePanel?: () => void;
  // Đơn thuốc đã lưu trong hồ sơ (tab "Đơn thuốc của tôi") để chọn nhập vào panel
  // này. 0 đơn -> ẩn hẳn nút; đúng 1 đơn -> bấm là nhập luôn (như hành vi cũ);
  // từ 2 đơn trở lên -> hiện danh sách để chọn đúng 1 đơn.
  savedPrescriptions?: PatientPrescription[];
  onImportFrom?: (prescriptionId: string) => void;
  // Cho phép đổi tên đơn thuốc qua nút sửa (bấm mới cho sửa). Không truyền prop
  // này thì tên đơn hiển thị tĩnh, không sửa được (VD: bàn cân tương tác của bệnh nhân).
  onRename?: (label: string) => void;
  inputId: string;
  // Bắt buộc để gọi POST /prescriptions/scan (yêu cầu đăng nhập). Không có token
  // (khách chưa đăng nhập) -> nút "Quét OCR" bị khóa thay vì gọi API rồi nhận 401.
  token?: string;
  // Điều khiển modal duyệt kết quả OCR hiện điểm khớp dạng số ("pharmacist") hay
  // chỉ nhãn chữ ("patient", mặc định) - xem PrescriptionScanModal.
  audience?: "patient" | "pharmacist";
};

export default function PrescriptionPanel({ label, drugs, search, onAdd, onRemoveDrug, onRemovePanel, savedPrescriptions, onImportFrom, onRename, inputId, token, audience }: PrescriptionPanelProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [importPickerOpen, setImportPickerOpen] = useState(false);
  const importPickerRef = useRef<HTMLDivElement>(null);
  const [editingLabel, setEditingLabel] = useState(false);
  const [draftLabel, setDraftLabel] = useState(label);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<ScanPrescriptionResponse | null>(null);
  const [scannedImageFile, setScannedImageFile] = useState<File | null>(null);

  useEffect(() => setDraftLabel(label), [label]);

  useEffect(() => {
    if (query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => search(query.trim()).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    if (!importPickerOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (importPickerRef.current && !importPickerRef.current.contains(e.target as Node)) setImportPickerOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [importPickerOpen]);

  function handleImportClick() {
    if (!savedPrescriptions || !onImportFrom) return;
    if (savedPrescriptions.length === 1) onImportFrom(savedPrescriptions[0].id);
    else setImportPickerOpen((open) => !open);
  }

  function add(name: string, known = true) {
    onAdd(name, known);
    setQuery("");
    setSuggestions([]);
  }

  function saveLabel() {
    const trimmed = draftLabel.trim();
    setEditingLabel(false);
    if (!trimmed || trimmed === label) { setDraftLabel(label); return; }
    onRename?.(trimmed);
  }

  async function handleScanFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // cho phép chọn lại đúng file đó lần sau
    if (!file || !token) return;
    setScanError(null);
    setScanning(true);
    setScannedImageFile(file);
    try {
      const result = await scanPrescription(file, token);
      setScanResult(result);
    } catch (err) {
      setScanError(err instanceof ApiError ? err.message : "Không thể quét ảnh lúc này. Vui lòng thử lại.");
    } finally {
      setScanning(false);
    }
  }

  // Panel này chỉ sống trong session (bàn cân tương tác / tra cứu của dược sĩ), không
  // ghi vào hồ sơ ai cả - nên chẩn đoán đọc được chỉ hiển thị để đối chiếu, phần chọn
  // bệnh nền bị tắt (canAddConditions không được truyền) và diseaseIds luôn rỗng.
  function confirmScannedDrugs(selected: { name: string; known: boolean }[]) {
    selected.forEach((drug) => add(drug.name, drug.known));
    setScanResult(null);
    setScannedImageFile(null);
  }

  return (
    <div className="prescription-panel panel">
      <div className="prescription-panel__header">
        {editingLabel && onRename ? (
          <input
            className="prescription-panel__label-input"
            value={draftLabel}
            onChange={(e) => setDraftLabel(e.target.value)}
            onBlur={saveLabel}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") { setDraftLabel(label); setEditingLabel(false); }
            }}
            aria-label="Tên đơn thuốc"
            autoFocus
          />
        ) : (
          <h3>{label}</h3>
        )}
        <div className="prescription-panel__header-actions">
          {onRename && !editingLabel && (
            <button type="button" className="prescription-panel__edit" onClick={() => setEditingLabel(true)} aria-label="Sửa tên đơn thuốc" title="Sửa tên đơn thuốc">
              <MaterialIcon name="edit" size={16} />
            </button>
          )}
          {onRemovePanel && (
            <button type="button" className="prescription-panel__remove" onClick={onRemovePanel} aria-label={`Xóa ${label}`}>
              <MaterialIcon name="close" size={18} />
            </button>
          )}
        </div>
      </div>
      <div className="prescription-panel__actions">
        {savedPrescriptions && savedPrescriptions.length > 0 && onImportFrom && (
          <div className="prescription-panel__import" ref={importPickerRef}>
            <button type="button" className="prescription-panel__tool" onClick={handleImportClick} title="Nhập từ hồ sơ thuốc đang dùng">
              <MaterialIcon name="download" size={16} /><span>Nhập từ hồ sơ</span>
            </button>
            {importPickerOpen && (
              <ul className="prescription-panel__import-menu">
                {savedPrescriptions.map((p) => (
                  <li key={p.id} onClick={() => { onImportFrom(p.id); setImportPickerOpen(false); }}>
                    <div><strong>{p.label}</strong><small>{p.medications.length} thuốc</small></div>
                    <MaterialIcon name="chevron_right" size={17} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <button
          type="button"
          className="prescription-panel__tool"
          disabled={!token || scanning}
          title={token ? "Chụp ảnh đơn thuốc" : "Đăng nhập để dùng tính năng chụp OCR"}
          onClick={() => cameraInputRef.current?.click()}
        >
          <MaterialIcon name="photo_camera" size={16} /><span>{scanning ? "Đang quét..." : "Chụp ảnh"}</span>
        </button>
        <button
          type="button"
          className="prescription-panel__tool"
          disabled={!token || scanning}
          title={token ? "Tải ảnh từ máy" : "Đăng nhập để tải ảnh"}
          onClick={() => fileInputRef.current?.click()}
        >
          <MaterialIcon name="image" size={16} /><span>Tải ảnh</span>
        </button>
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => void handleScanFile(e)}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => void handleScanFile(e)}
        />
      </div>

      {scanning && (
        <div className="ocr-scan-loading" role="status">
          <MediFox variant="loading" className="ocr-scan-loading__fox" />
          <strong>Cáo Medi đang đọc đơn thuốc của bạn…</strong>
          <span>Có thể mất vài giây, đừng tắt trang nhé.</span>
        </div>
      )}
      {scanError && <p className="error-text" role="alert">{scanError}</p>}
      {scanResult && (
        <PrescriptionScanModal
          result={scanResult}
          onConfirm={confirmScannedDrugs}
          onClose={() => { setScanResult(null); setScannedImageFile(null); }}
          imageFile={scannedImageFile || undefined}
          search={search}
          audience={audience}
        />
      )}

      <div className="interaction-search__input icon-input-spacing">
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
            <li
              key={item.id}
              className={drugs.some((drug) => drug.name.toLowerCase() === item.ten_thuoc.toLowerCase()) ? "interaction-suggestion--selected" : undefined}
              aria-disabled={drugs.some((drug) => drug.name.toLowerCase() === item.ten_thuoc.toLowerCase())}
              onClick={() => {
                if (!drugs.some((drug) => drug.name.toLowerCase() === item.ten_thuoc.toLowerCase())) add(item.ten_thuoc);
              }}
            >
              <div><strong>{item.ten_thuoc}</strong><small>{drugs.some((drug) => drug.name.toLowerCase() === item.ten_thuoc.toLowerCase()) ? "Đã chọn trong đơn" : "Thuốc trong cơ sở dữ liệu"}</small></div>
              <MaterialIcon name={drugs.some((drug) => drug.name.toLowerCase() === item.ten_thuoc.toLowerCase()) ? "check" : "add_circle_outline"} size={19} />
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
