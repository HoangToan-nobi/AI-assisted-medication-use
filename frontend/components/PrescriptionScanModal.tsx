"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import MaterialIcon from "@/components/MaterialIcon";
import type { ScanPrescriptionResponse } from "@/lib/api";

type Selection =
  | { mode: "skip" }
  | { mode: "suggested" }
  | { mode: "alt"; index: number }
  | { mode: "manual"; text: string };

type PrescriptionScanModalProps = {
  result: ScanPrescriptionResponse;
  onConfirm: (drugs: { name: string; known: boolean }[], diseaseIds: number[]) => void;
  onClose: () => void;
  imageFile?: File;
  // Bệnh nền thuộc về hồ sơ người dùng, không thuộc về một đơn thuốc cụ thể - nên
  // chỉ nơi có quyền ghi hồ sơ (trang "Đơn thuốc của tôi") mới truyền prop này và
  // cho tick chọn. Nơi khác (bàn cân tương tác, tra cứu của dược sĩ) vẫn thấy chẩn
  // đoán đọc được nhưng ở dạng chỉ đọc.
  canAddConditions?: boolean;
  // Dược sĩ hiểu và cần điểm khớp (0.87...) để quyết định nhanh; bệnh nhân thì
  // không - hiện số cho họ chỉ gây nhiễu (đo lường thực tế trên đơn thật: dòng hệ
  // thống tự tin nhất - 0.87 - lại là dòng SAI). Mặc định "patient": chỉ hiện nhãn
  // "Đề xuất"/"Ứng viên khác" bằng chữ, không hiện %.
  audience?: "patient" | "pharmacist";
};

// Modal duyệt kết quả OCR - BẮT BUỘC có bước này trước khi thêm bất kỳ thuốc nào
// vào đơn. Độ chính xác khớp tên hiện tại ~67%: dòng hệ thống tự tin nhất có thể là
// dòng sai (ví dụ "Đại tần giao" bị khớp thành "Tần giao" điểm 0.87, trong khi ứng
// viên đúng "Đại Tần Giao" chỉ xếp hạng 2) - nên mỗi dòng mặc định "Bỏ qua", không
// dòng nào được tick sẵn, và alternatives luôn hiển thị chứ không phải chi tiết ẩn.
export default function PrescriptionScanModal({ result, onConfirm, onClose, imageFile, canAddConditions = false, audience = "patient" }: PrescriptionScanModalProps) {
  const [selections, setSelections] = useState<Selection[]>(() => result.drugs.map(() => ({ mode: "skip" })));
  // Khác thuốc (mỗi dòng đúng một thuốc -> radio): một dòng chẩn đoán có thể chứa
  // nhiều bệnh thật cùng lúc - "Bệnh kèm theo: ;I10;E11: ;Bệnh tăng huyết áp vô
  // căn;Bệnh đái tháo đường..." là một dòng nhưng hai bệnh, và OCR không phải lúc
  // nào cũng tách được chúng ra. Vì vậy dùng checkbox, tick được nhiều.
  // Vẫn không tick sẵn gì: tên trên đơn dài hơn tên trong CSDL nên ứng viên hạng
  // nhất vẫn có thể sai.
  const [diseaseSelections, setDiseaseSelections] = useState<number[][]>(
    () => (result.diseases ?? []).map(() => [])
  );
  const [imagePreview, setImagePreview] = useState<string>("");
  const [imageZoomed, setImageZoomed] = useState(false);

  if (imageFile && !imagePreview) {
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(imageFile);
  }

  function setSelection(rowIndex: number, selection: Selection) {
    setSelections((prev) => prev.map((s, i) => (i === rowIndex ? selection : s)));
  }

  function toggleDisease(rowIndex: number, diseaseId: number) {
    setDiseaseSelections((prev) =>
      prev.map((ids, i) => {
        if (i !== rowIndex) return ids;
        return ids.includes(diseaseId) ? ids.filter((id) => id !== diseaseId) : [...ids, diseaseId];
      }),
    );
  }

  function handleConfirm() {
    const drugs: { name: string; known: boolean }[] = [];
    result.drugs.forEach((row, index) => {
      const selection = selections[index];
      if (selection.mode === "skip") return;
      if (selection.mode === "suggested" && row.suggested_name) {
        drugs.push({ name: row.suggested_name, known: true });
      } else if (selection.mode === "alt") {
        const name = row.alternatives[selection.index];
        if (name) drugs.push({ name, known: true });
      } else if (selection.mode === "manual") {
        const name = selection.text.trim();
        if (name) drugs.push({ name, known: false });
      }
    });
    // Cùng một bệnh có thể được tick ở hai dòng chẩn đoán khác nhau (đơn ghi lặp) -
    // gộp lại để không gửi id trùng.
    onConfirm(drugs, Array.from(new Set(diseaseSelections.flat())));
  }

  const selectedCount = selections.filter((s) => s.mode !== "skip").length;
  const selectedDiseaseCount = new Set(diseaseSelections.flat()).size;
  const diseases = result.diseases ?? [];

  // Portal ra document.body: modal có thể render lồng sâu bên trong
  // PrescriptionPanel, mà .prescription-panel có transform lúc :hover (hiệu ứng
  // nhấc thẻ có sẵn của app) - transform trên ancestor bất kỳ biến nó thành
  // containing block cho position:fixed, khiến modal bị định vị theo ancestor đó
  // thay vì viewport. Portal thoát khỏi cây DOM đó nên luôn định vị đúng.
  return createPortal(
    <div className="ocr-scan-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="ocr-scan-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ocr-scan-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="ocr-scan-modal__header">
          <div>
            <span className="ocr-scan-modal__eyebrow">CÁO MEDI ĐÃ ĐỌC XONG</span>
            <h2 id="ocr-scan-title">Duyệt thuốc nhận diện được</h2>
            <p>
              Đối chiếu nguyên văn OCR với tờ đơn trên tay, chọn đúng tên thuốc cho từng dòng rồi bấm xác nhận.
              Chưa dòng nào được thêm vào đơn.
            </p>
          </div>
          <button type="button" className="ocr-scan-modal__close" onClick={onClose} aria-label="Đóng">
            <MaterialIcon name="close" size={20} />
          </button>
        </header>

        <div className="ocr-scan-content">
          {imagePreview && (
            <>
              <aside className="ocr-scan-preview" onClick={() => setImageZoomed(true)} role="button" tabIndex={0} aria-label="Phóng to ảnh">
                <img src={imagePreview} alt="Đơn thuốc đã chụp" className="ocr-scan-preview__image" />
                <div className="ocr-scan-preview__zoom-hint">
                  <MaterialIcon name="zoom_in" size={16} />
                </div>
              </aside>

              {imageZoomed &&
                createPortal(
                  <div
                    className="ocr-scan-zoom-backdrop"
                    onClick={() => setImageZoomed(false)}
                    role="presentation"
                  >
                    <div className="ocr-scan-zoom-modal" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="ocr-scan-zoom-close"
                        onClick={() => setImageZoomed(false)}
                        aria-label="Đóng"
                      >
                        <MaterialIcon name="close" size={24} />
                      </button>
                      <img src={imagePreview} alt="Đơn thuốc phóng to" className="ocr-scan-zoom-image" />
                    </div>
                  </div>,
                  document.body
                )}
            </>
          )}

          <div className="ocr-scan-lists">
          {diseases.length > 0 && (
            <section className="ocr-scan-diseases">
              <p className="ocr-scan-diseases__label">
                Chẩn đoán đọc được trên đơn
                {canAddConditions && <span> — chọn để thêm vào bệnh nền của bạn</span>}
              </p>
              <ul className="ocr-scan-rows">
                {diseases.map((disease, index) => {
                  const candidates = [
                    ...(disease.suggested ? [{ item: disease.suggested, top: true }] : []),
                    ...disease.alternatives.map((item) => ({ item, top: false })),
                  ];
                  const selectedIds = diseaseSelections[index] ?? [];
                  return (
                    <li className="ocr-scan-row" key={index}>
                      <div className="ocr-scan-row__ocr">
                        {disease.icd_code && <span className="ocr-scan-row__number">{disease.icd_code}</span>}
                        <div>
                          <span className="ocr-scan-row__label">Nguyên văn trên đơn</span>
                          <p>{disease.ocr_text}</p>
                        </div>
                      </div>

                      {candidates.length === 0 ? (
                        <p className="ocr-scan-row__unmatched">
                          <MaterialIcon name="info" size={15} />
                          Chưa có bệnh nào trong danh mục khớp với dòng này.
                        </p>
                      ) : !canAddConditions ? (
                        <div className="ocr-scan-row__options">
                          {candidates.map(({ item, top }) => (
                            <div key={item.id} className="ocr-scan-option ocr-scan-option--readonly">
                              <span className="ocr-scan-option__name">{item.ten_benh}</span>
                              <span className={`ocr-scan-option__tag ${top ? "ocr-scan-option__tag--top" : ""}`}>
                                {top ? "Đề xuất" : "Ứng viên khác"}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        // Checkbox chứ không radio: tick được nhiều bệnh trên cùng
                        // một dòng. Không tick gì tức là bỏ qua dòng đó, nên không
                        // cần lựa chọn "Bỏ qua" riêng như bên thuốc.
                        <div className="ocr-scan-row__options">
                          {candidates.map(({ item, top }) => (
                            <label
                              key={item.id}
                              className={`ocr-scan-option ${selectedIds.includes(item.id) ? "ocr-scan-option--selected" : ""}`}
                            >
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(item.id)}
                                onChange={() => toggleDisease(index, item.id)}
                              />
                              <span className="ocr-scan-option__name">{item.ten_benh}</span>
                              <span className={`ocr-scan-option__tag ${top ? "ocr-scan-option__tag--top" : ""}`}>
                                {top ? "Đề xuất" : "Ứng viên khác"}
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {result.drugs.length === 0 ? (
            <p className="ocr-scan-modal__empty">Không đọc được dòng thuốc nào trong ảnh này. Hãy chụp lại rõ hơn hoặc nhập tên thuốc thủ công.</p>
          ) : (
            <ul className="ocr-scan-rows">
            {result.drugs.map((row, index) => {
              const selection = selections[index];
              const radioName = `ocr-scan-row-${index}`;
              return (
                <li className="ocr-scan-row" key={row.row_number ?? index}>
                  <div className="ocr-scan-row__ocr">
                    {row.row_number != null && <span className="ocr-scan-row__number">#{row.row_number}</span>}
                    <div>
                      <span className="ocr-scan-row__label">Nguyên văn OCR</span>
                      <p>{row.ocr_text || "(không đọc được dòng này)"}</p>
                    </div>
                  </div>

                  <div className="ocr-scan-row__options">
                    {row.suggested_name && (
                      <label className={`ocr-scan-option ${selection.mode === "suggested" ? "ocr-scan-option--selected" : ""}`}>
                        <input type="radio" name={radioName} checked={selection.mode === "suggested"} onChange={() => setSelection(index, { mode: "suggested" })} />
                        <span className="ocr-scan-option__name">{row.suggested_name}</span>
                        <span className="ocr-scan-option__tag ocr-scan-option__tag--top">
                          {audience === "pharmacist" ? `Đề xuất · ${row.score.toFixed(2)}` : "Đề xuất"}
                        </span>
                      </label>
                    )}
                    {row.alternatives.map((alt, altIndex) => (
                      <label key={alt} className={`ocr-scan-option ${selection.mode === "alt" && selection.index === altIndex ? "ocr-scan-option--selected" : ""}`}>
                        <input type="radio" name={radioName} checked={selection.mode === "alt" && selection.index === altIndex} onChange={() => setSelection(index, { mode: "alt", index: altIndex })} />
                        <span className="ocr-scan-option__name">{alt}</span>
                        <span className="ocr-scan-option__tag">Ứng viên khác</span>
                      </label>
                    ))}
                    <label className={`ocr-scan-option ocr-scan-option--manual ${selection.mode === "manual" ? "ocr-scan-option--selected" : ""}`}>
                      <input type="radio" name={radioName} checked={selection.mode === "manual"} onChange={() => setSelection(index, { mode: "manual", text: selection.mode === "manual" ? selection.text : "" })} />
                      <input
                        type="text"
                        placeholder="Nhập tên thuốc khác..."
                        value={selection.mode === "manual" ? selection.text : ""}
                        onFocus={() => { if (selection.mode !== "manual") setSelection(index, { mode: "manual", text: "" }); }}
                        onChange={(e) => setSelection(index, { mode: "manual", text: e.target.value })}
                      />
                    </label>
                    <label className={`ocr-scan-option ocr-scan-option--skip ${selection.mode === "skip" ? "ocr-scan-option--selected" : ""}`}>
                      <input type="radio" name={radioName} checked={selection.mode === "skip"} onChange={() => setSelection(index, { mode: "skip" })} />
                      <span className="ocr-scan-option__name">Bỏ qua dòng này</span>
                    </label>
                  </div>

                  {!row.suggested_name && (
                    <p className="ocr-scan-row__unmatched">
                      <MaterialIcon name="info" size={15} />
                      Chưa có trong danh mục — nhập tên thủ công ở trên nếu muốn thêm.
                    </p>
                  )}
                </li>
              );
            })}
            </ul>
          )}
          </div>
        </div>

        <footer className="ocr-scan-modal__footer">
          <button type="button" className="ocr-scan-modal__cancel" onClick={onClose}>Hủy</button>
          <button
            type="button"
            className="ocr-scan-modal__confirm"
            onClick={handleConfirm}
            disabled={selectedCount === 0 && selectedDiseaseCount === 0}
          >
            <MaterialIcon name="check" size={18} />
            {/* Nêu đúng thứ sắp xảy ra: chỉ tick bệnh mà nút vẫn ghi "0 thuốc" thì
                đọc như sắp có gì đó bị thêm nhầm vào đơn. */}
            {selectedCount > 0 && selectedDiseaseCount > 0
              ? `Thêm ${selectedCount} thuốc và ${selectedDiseaseCount} bệnh nền`
              : selectedDiseaseCount > 0
                ? `Thêm ${selectedDiseaseCount} bệnh nền vào hồ sơ`
                : `Thêm ${selectedCount > 0 ? selectedCount : ""} thuốc đã chọn vào đơn`}
          </button>
        </footer>
      </section>
    </div>,
    document.body
  );
}
