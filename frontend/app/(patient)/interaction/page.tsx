"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import PrescriptionPanel from "@/components/PrescriptionPanel";
import InteractionResultView from "@/components/graph/InteractionResultView";
import { ApiError, checkGuestProducts, checkProducts, listPatientPrescriptions, searchGuestProducts, searchProducts, type MedicationCheckResponse, type PatientPrescription } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { createPrescription, mergeSavedIntoPrescriptions, mergedDrugNames, nonEmptyPrescriptions, toPrescriptionCheckInput, type Prescription } from "@/lib/prescription";

// Lưu tạm các đơn/thuốc đang nhập dở và kết quả phân tích gần nhất trong phiên
// trình duyệt, để reload trang hoặc chuyển sang tab khác rồi quay lại Tra cứu
// tương tác không làm mất dữ liệu/kết quả đã có.
const DRAFT_KEY = "medguard_interaction_draft";
const RESULT_KEY = "medguard_interaction_result";
// Ảnh chụp danh sách đơn thuốc (đã lọc rỗng) TẠI THỜI ĐIỂM chạy check tạo ra
// RESULT_KEY - phải dùng đúng danh sách này (không phải state `prescriptions` đang
// sống, có thể đã bị sửa tiếp) để dựng đồ thị, vì chỉ số đơn trong đó khớp với
// don_a_index/don_b_index mà backend trả về trong result.prescription_explanations.
const RESULT_PRESCRIPTIONS_KEY = "medguard_interaction_result_prescriptions";

function loadDraftPrescriptions(): Prescription[] | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : null;
  } catch {
    return null;
  }
}

function loadDraftResult(): MedicationCheckResponse | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(RESULT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MedicationCheckResponse;
  } catch {
    return null;
  }
}

function loadDraftResultPrescriptions(): Prescription[] | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(RESULT_PRESCRIPTIONS_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : null;
  } catch {
    return null;
  }
}

function InteractionPageContent() {
  const session = getSession();
  // Chỉ tự nhập thuốc từ hồ sơ khi được điều hướng tới từ nút "Kiểm tra tương tác"
  // (ví dụ ở trang Hồ sơ, gắn ?import=profile) - không tự ý ghi đè khi người dùng
  // chỉ đơn thuần bấm vào tab "Tương tác" trên thanh điều hướng.
  const shouldImportFromProfile = useSearchParams().get("import") === "profile";
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(() => loadDraftPrescriptions() ?? [createPrescription(1)]);
  const [savedPrescriptions, setSavedPrescriptions] = useState<PatientPrescription[]>([]);
  const [result, setResult] = useState<MedicationCheckResponse | null>(() => loadDraftResult());
  const [resultPrescriptions, setResultPrescriptions] = useState<Prescription[] | null>(() => loadDraftResultPrescriptions());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const boardMode = prescriptions.length > 1;
  const primary = prescriptions[0];

  useEffect(() => {
    if (!session) return;
    listPatientPrescriptions(session.userId, session.accessToken)
      .then((saved) => {
        setSavedPrescriptions(saved);
        // Chỉ điều hướng tới đây kèm ?import=profile (VD từ nút "Kiểm tra tương tác"
        // ở tab Đơn thuốc của tôi) mới tự nạp đơn đã lưu thành các panel tương ứng -
        // bấm thẳng vào tab Tương tác không tự ý ghi đè bàn cân. Gộp theo nhãn đơn
        // (mergeSavedIntoPrescriptions) thay vì thay thế toàn bộ, để import nhiều
        // lần liên tiếp nối tiếp nhau vào bàn cân thay vì xóa mất lần import trước.
        if (shouldImportFromProfile && saved.length > 0) setPrescriptions((prev) => mergeSavedIntoPrescriptions(prev, saved));
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(prescriptions));
  }, [prescriptions]);
  useEffect(() => {
    if (result) window.sessionStorage.setItem(RESULT_KEY, JSON.stringify(result));
    else window.sessionStorage.removeItem(RESULT_KEY);
  }, [result]);
  useEffect(() => {
    if (resultPrescriptions) window.sessionStorage.setItem(RESULT_PRESCRIPTIONS_KEY, JSON.stringify(resultPrescriptions));
    else window.sessionStorage.removeItem(RESULT_PRESCRIPTIONS_KEY);
  }, [resultPrescriptions]);

  const searchFn = (q: string) => (session ? searchProducts(q, session.accessToken) : searchGuestProducts(q));

  function addDrugTo(prescriptionId: string, name: string, known = true) {
    setPrescriptions((prev) => prev.map((p) => {
      if (p.id !== prescriptionId) return p;
      if (p.drugs.some((d) => d.name.toLowerCase() === name.toLowerCase())) return p;
      return { ...p, drugs: [...p.drugs, { name, known }] };
    }));
    setResult(null);
  }

  function removeDrugFrom(prescriptionId: string, name: string) {
    setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, drugs: p.drugs.filter((d) => d.name !== name) } : p)));
    setResult(null);
  }

  function addPrescription() {
    setPrescriptions((prev) => [...prev, createPrescription(prev.length + 1)]);
  }

  function removePrescription(id: string) {
    setPrescriptions((prev) => (prev.length <= 1 ? prev : prev.filter((p) => p.id !== id)));
    setResult(null);
  }

  function importFromProfile(prescriptionId: string, sourcePrescriptionId: string) {
    const source = savedPrescriptions.find((p) => p.id === sourcePrescriptionId);
    if (!source) return;
    setPrescriptions((prev) => prev.map((p) => {
      if (p.id !== prescriptionId) return p;
      const existing = new Set(p.drugs.map((d) => d.name.toLowerCase()));
      const toAdd = source.medications.filter((item) => !existing.has(item.ten_thuoc.toLowerCase())).map((item) => ({ name: item.ten_thuoc, known: true }));
      return toAdd.length ? { ...p, drugs: [...p.drugs, ...toAdd] } : p;
    }));
    setResult(null);
  }

  function resetAll() {
    if (!window.confirm("Xóa toàn bộ đơn thuốc, thuốc đã nhập và kết quả tra cứu hiện tại?")) return;
    setPrescriptions([createPrescription(1)]);
    setResult(null);
    setResultPrescriptions(null);
    setError(null);
  }

  async function runCheck(e?: FormEvent) {
    e?.preventDefault();
    const activePrescriptions = nonEmptyPrescriptions(prescriptions);
    if (mergedDrugNames(activePrescriptions).length < 2) { setError("Hãy chọn ít nhất 2 thuốc để phân tích tương tác."); return; }
    setError(null); setLoading(true);
    const payload = toPrescriptionCheckInput(activePrescriptions);
    try {
      const data = session ? await checkProducts(payload, session.accessToken) : await checkGuestProducts(payload);
      setResult(data);
      setResultPrescriptions(activePrescriptions);
      window.sessionStorage.setItem("medguard_last_check", JSON.stringify(data));
    }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không thể phân tích tương tác lúc này."); }
    finally { setLoading(false); }
  }

  return <main className="interaction-page">{!session && <div className="guest-mode-banner"><MaterialIcon name="visibility" size={18} /><span>Chế độ khách: kết quả chỉ hiển thị tạm thời và không được lưu vào lịch sử.</span></div>}
    <section className="page-intro page-intro--with-action">
      <div><p className="eyebrow">PHÂN TÍCH AN TOÀN</p><h1>Kiểm Tra Tương Tác Thuốc</h1><p>Thêm thuốc mới vào đơn hiện tại để xem phân tích tương tác tức thì, hoặc thêm nhiều đơn thuốc để so sánh cùng lúc.</p></div>
      {(result || boardMode || primary.drugs.length > 0) && (
        <button type="button" className="interaction-reset" onClick={resetAll}>
          <MaterialIcon name="restart_alt" size={17} /> Làm mới
        </button>
      )}
    </section>

    {error && <p className="error-text" role="alert">{error}</p>}
    {result && (result.unknown_products?.length ?? 0) > 0 && <div className="guest-mode-banner"><MaterialIcon name="info" size={18} /><span>Không tìm thấy trong CSDL: {result.unknown_products!.join(", ")}.</span></div>}

    <section className="prescription-board-wrap">
      <div className="prescription-board prescription-board--slider">
        {prescriptions.map((p) => (
          <PrescriptionPanel key={p.id} label={p.label} drugs={p.drugs} search={searchFn}
            onAdd={(name, known) => addDrugTo(p.id, name, known)}
            onRemoveDrug={(name) => removeDrugFrom(p.id, name)}
            onRemovePanel={boardMode ? () => removePrescription(p.id) : undefined}
            savedPrescriptions={session ? savedPrescriptions : undefined}
            onImportFrom={session ? (sourceId) => importFromProfile(p.id, sourceId) : undefined}
            inputId={`prescription-search-${p.id}`} />
        ))}
        <button type="button" className="prescription-board__add" onClick={addPrescription}>
          <MaterialIcon name="add_circle" size={26} /><span>Thêm đơn thuốc</span>
        </button>
      </div>
      <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || mergedDrugNames(prescriptions).length < 2}>
        <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
      </button>
    </section>

    {result && <InteractionResultView result={result} prescriptions={resultPrescriptions ?? []} session={session} />}
  </main>;
}

export default function InteractionPage() {
  return <Suspense fallback={<main className="interaction-page"><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}><InteractionPageContent /></Suspense>;
}
