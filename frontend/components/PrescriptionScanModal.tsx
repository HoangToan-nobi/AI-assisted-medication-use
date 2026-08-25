"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import MaterialIcon from "@/components/MaterialIcon";
import type { ProductSearchResult, ScanPrescriptionResponse } from "@/lib/api";

// Một dòng thuốc sau khi người dùng duyệt: tên đã chốt (mặc định là ứng viên điểm
// cao nhất mà OCR trả về) hoặc null nếu chưa có/chưa chọn được ứng viên nào. Chỉ
// tên lấy từ CSDL (ứng viên gốc hoặc kết quả tìm kiếm khi bấm Sửa) mới được chốt ở
// đây - không còn đường nhập tay tự do như trước, nên dòng nào chốt được tên là
// chắc chắn khớp CSDL.
type DrugRowState = {
  removed: boolean;
  chosenName: string | null;
};

type PrescriptionScanModalProps = {
  result: ScanPrescriptionResponse;
  onConfirm: (drugs: { name: string; known: boolean }[], diseaseIds: number[]) => void;
  onClose: () => void;
  imageFile?: File;
  // Dùng để tìm thuốc thay thế khi người dùng bấm "Sửa" trên một dòng thuốc - cùng
  // hàm tìm kiếm đang dùng cho ô tìm thuốc chính của panel, đảm bảo tên chọn lại
  // luôn là tên có thật trong CSDL.
  search: (query: string) => Promise<ProductSearchResult[]>;
  // Bệnh nền thuộc về hồ sơ người dùng, không thuộc về một đơn thuốc cụ thể - nên
  // chỉ nơi có quyền ghi hồ sơ (trang "Đơn thuốc của tôi") mới truyền prop này và
  // cho tick chọn. Nơi khác (bàn cân tương tác, tra cứu của dược sĩ) vẫn thấy chẩn
  // đoán đọc được nhưng ở dạng chỉ đọc.
  canAddConditions?: boolean;
  // Dược sĩ hiểu và cần điểm khớp (0.87...) để quyết định nhanh; bệnh nhân thì
  // không - hiện số cho họ chỉ gây nhiễu. Chỉ hiện điểm khi dòng vẫn đang dùng đúng
  // ứng viên gốc (chưa bị Sửa lại), vì sau khi sửa thì điểm ứng viên gốc không còn
  // ý nghĩa gì với tên mới.
  audience?: "patient" | "pharmacist";
};

// Modal duyệt kết quả OCR - BẮT BUỘC có bước này trước khi thêm bất kỳ thuốc nào
// vào đơn. Độ chính xác khớp tên hiện tại ~67%: dòng hệ thống tự tin nhất vẫn có
// thể sai (ví dụ "Đại tần giao" bị khớp thành "Tần giao"). Ứng viên điểm cao nhất
// chỉ được tick sẵn khi backend đánh giá là đủ tin cậy (known); dòng không đạt
// ngưỡng đó bắt đầu ở trạng thái trống - đỡ phải dò qua danh sách cho dòng đã chắc
// chắn, nhưng không âm thầm nhận một cái tên chỉ là "giống nhất" trong toàn bộ CSDL.
// "Sửa"/"Xóa" xử lý phần còn lại - Sửa mở tìm kiếm toàn bộ CSDL chứ không chỉ 2-3
// ứng viên gợi ý, Xóa bỏ hẳn dòng nếu không cần.
export default function PrescriptionScanModal({ result, onConfirm, onClose, imageFile, search, canAddConditions = false, audience = "patient" }: PrescriptionScanModalProps) {
  // Chỉ tick sẵn khi backend đã coi ứng viên là đủ tin cậy (known, điểm >=0.75).
  // Dưới ngưỡng đó, tên gợi ý có thể chỉ là thứ giống nhất trong toàn bộ CSDL
  // dù ảnh chẳng liên quan gì đến thuốc (ví dụ chụp một tấm QR khảo sát) - để
  // trống buộc người dùng tự bấm "Sửa" thay vì âm thầm thêm nhầm thuốc vào đơn.
  const [drugRows, setDrugRows] = useState<DrugRowState[]>(
    () => result.drugs.map((row) => ({ removed: false, chosenName: row.known ? row.suggested_name : null })),
  );
  // Chỉ một dòng được sửa cùng lúc - đơn giản hơn so với giữ ô tìm kiếm riêng cho
  // từng dòng, và cũng khớp cách người dùng thực tế duyệt: sửa xong dòng này mới
  // sang dòng khác.
  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [editQuery, setEditQuery] = useState("");
  const [editSuggestions, setEditSuggestions] = useState<ProductSearchResult[]>([]);

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

  useEffect(() => {
    if (editingRow === null || editQuery.trim().length < 2) { setEditSuggestions([]); return; }
    const timer = setTimeout(
      () => search(editQuery.trim()).then(setEditSuggestions).catch(() => setEditSuggestions([])),
      250,
    );
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editQuery, editingRow]);

  function startEdit(rowIndex: number) {
    setEditingRow(rowIndex);
    setEditQuery("");
    setEditSuggestions([]);
  }

  function cancelEdit() {
    setEditingRow(null);
    setEditQuery("");
    setEditSuggestions([]);
  }

  function pickDrug(rowIndex: number, name: string) {
    setDrugRows((prev) => prev.map((r, i) => (i === rowIndex ? { removed: false, chosenName: name } : r)));
    cancelEdit();
  }

  function removeDrugRow(rowIndex: number) {
    setDrugRows((prev) => prev.map((r, i) => (i === rowIndex ? { ...r, removed: true } : r)));
    if (editingRow === rowIndex) cancelEdit();
  }

  function restoreDrugRow(rowIndex: number) {
    setDrugRows((prev) => prev.map((r, i) => (i === rowIndex ? { ...r, removed: false } : r)));
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
    drugRows.forEach((row) => {
      // Không chốt được tên (chưa có ứng viên gốc và chưa sửa) hoặc bị xóa -> không
      // lưu, đúng như yêu cầu: chỉ tên khớp CSDL mới được thêm vào đơn.
      if (row.removed || !row.chosenName) return;
      drugs.push({ name: row.chosenName, known: true });
    });
    // Cùng một bệnh có thể được tick ở hai dòng chẩn đoán khác nhau (đơn ghi lặp) -
    // gộp lại để không gửi id trùng.
    onConfirm(drugs, Array.from(new Set(diseaseSelections.flat())));
  }

  const selectedCount = drugRows.filter((r) => !r.removed && r.chosenName).length;
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
              Đối chiếu nguyên văn OCR với tờ đơn trên tay. Mỗi dòng đã chọn sẵn thuốc khớp nhất -
              bấm &quot;Sửa&quot; nếu sai, &quot;Xóa&quot; nếu không cần dòng đó, rồi bấm xác nhận.
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
                    ...(disease.suggested ? [disease.suggested] : []),
                    ...disease.alternatives,
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
                          {candidates.map((item) => (
                            <div key={item.id} className="ocr-scan-option ocr-scan-option--readonly">
                              <span className="ocr-scan-option__name">{item.ten_benh}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        // Checkbox chứ không radio: tick được nhiều bệnh trên cùng
                        // một dòng. Không tick gì tức là bỏ qua dòng đó, nên không
                        // cần lựa chọn "Bỏ qua" riêng như bên thuốc.
                        <div className="ocr-scan-row__options">
                          {candidates.map((item) => (
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
            <>
              {/* Đọc được chữ nhưng không dòng nào khớp CSDL đủ tin cậy - khác
                  với case rỗng ở trên (không đọc được chữ gì). Thường là ảnh
                  chụp nhầm thứ không phải thuốc (hóa đơn, biển báo...). */}
              {result.drugs.every((row) => !row.known) && (
                <p className="ocr-scan-modal__empty">Không tìm thấy thuốc nào trong ảnh. Thử chụp lại rõ hơn hoặc nhập tay.</p>
              )}
              <ul className="ocr-scan-rows">
            {result.drugs.map((row, index) => {
              const state = drugRows[index];
              const isEditing = editingRow === index;
              return (
                <li className="ocr-scan-row" key={row.row_number ?? index}>
                  <div className="ocr-scan-row__ocr">
                    {row.row_number != null && <span className="ocr-scan-row__number">#{row.row_number}</span>}
                    <div>
                      <span className="ocr-scan-row__label">Nguyên văn OCR</span>
                      <p>{row.ocr_text || "(không đọc được dòng này)"}</p>
                    </div>
                  </div>

                  {state.removed ? (
                    <p className="ocr-scan-row__removed">
                      <MaterialIcon name="info" size={15} />
                      Đã xóa dòng thuốc này.
                      <button type="button" onClick={() => restoreDrugRow(index)}>Hoàn tác</button>
                    </p>
                  ) : isEditing ? (
                    <div className="ocr-scan-drug-edit">
                      <div className="ocr-scan-option ocr-scan-option--manual">
                        <input
                          type="text"
                          autoFocus
                          placeholder="Nhập tên thuốc để tìm trong cơ sở dữ liệu..."
                          value={editQuery}
                          onChange={(e) => setEditQuery(e.target.value)}
                        />
                      </div>
                      {editSuggestions.length > 0 ? (
                        <ul className="ocr-scan-drug-edit__suggestions">
                          {editSuggestions.slice(0, 5).map((item) => (
                            <li key={item.id}>
                              <button type="button" className="ocr-scan-option" onClick={() => pickDrug(index, item.ten_thuoc)}>
                                <span className="ocr-scan-option__name">{item.ten_thuoc}</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : editQuery.trim().length >= 2 ? (
                        <p className="ocr-scan-drug-edit__empty">
                          Không tìm thấy thuốc nào khớp trong cơ sở dữ liệu. Chỉ thuốc có trong danh mục mới lưu được vào đơn.
                        </p>
                      ) : null}
                      <button type="button" className="ocr-scan-drug-edit__cancel" onClick={cancelEdit}>Hủy sửa</button>
                    </div>
                  ) : (
                    <div className="ocr-scan-drug-picked">
                      <div className="ocr-scan-option ocr-scan-option--readonly">
                        {state.chosenName ? (
                          <span className="ocr-scan-option__name">{state.chosenName}</span>
                        ) : (
                          <span className="ocr-scan-option__name ocr-scan-option__name--empty">Chưa nhận diện được thuốc</span>
                        )}
                        {state.chosenName && state.chosenName === row.suggested_name && audience === "pharmacist" && (
                          <span className="ocr-scan-option__tag ocr-scan-option__tag--top">{row.score.toFixed(2)}</span>
                        )}
                      </div>
                      <div className="ocr-scan-drug-actions">
                        <button type="button" onClick={() => startEdit(index)}>
                          <MaterialIcon name="edit" size={14} /><span>Sửa</span>
                        </button>
                        <button type="button" onClick={() => removeDrugRow(index)}>
                          <MaterialIcon name="delete_outline" size={14} /><span>Xóa</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {!state.removed && !isEditing && !state.chosenName && (
                    <p className="ocr-scan-row__unmatched">
                      <MaterialIcon name="info" size={15} />
                      Chưa có trong danh mục — bấm &quot;Sửa&quot; để tìm tên thuốc khác.
                    </p>
                  )}
                </li>
              );
            })}
              </ul>
            </>
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
