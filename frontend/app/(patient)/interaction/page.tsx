"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import PrescriptionPanel from "@/components/PrescriptionPanel";
import InteractionResultView from "@/components/graph/InteractionResultView";
import { ApiError, checkGuestProducts, checkProducts, listPatientMedications, searchGuestProducts, searchProducts, type MedicationCheckResponse, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { createPrescription, mergedDrugNames, nonEmptyPrescriptions, toPrescriptionCheckInput, type Prescription } from "@/lib/prescription";

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
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(() => loadDraftPrescriptions() ?? [createPrescription(1)]);
  const [result, setResult] = useState<MedicationCheckResponse | null>(() => loadDraftResult());
  const [resultPrescriptions, setResultPrescriptions] = useState<Prescription[] | null>(() => loadDraftResultPrescriptions());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const boardMode = prescriptions.length > 1;
  const primary = prescriptions[0];

  useEffect(() => {
    if (query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => (session ? searchProducts(query.trim(), session.accessToken) : searchGuestProducts(query.trim())).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  useEffect(() => {
    if (!session || !shouldImportFromProfile) return;
    listPatientMedications(session.userId, session.accessToken)
      .then((items) => setPrescriptions((prev) => prev.map((p, index) => (index === 0 ? { ...p, drugs: items.map((item) => ({ name: item.ten_thuoc, known: true })) } : p))))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldImportFromProfile]);
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

  function addDrug(name: string, known = true) {
    addDrugTo(primary.id, name, known);
    setQuery(""); setSuggestions([]);
  }

  function addPrescription() {
    setPrescriptions((prev) => [...prev, createPrescription(prev.length + 1)]);
    setQuery(""); setSuggestions([]);
  }

  function removePrescription(id: string) {
    setPrescriptions((prev) => (prev.length <= 1 ? prev : prev.filter((p) => p.id !== id)));
    setResult(null);
  }

  async function importFromProfile(prescriptionId: string) {
    if (!session) return;
    try {
      const items = await listPatientMedications(session.userId, session.accessToken);
      setPrescriptions((prev) => prev.map((p) => {
        if (p.id !== prescriptionId) return p;
        const existing = new Set(p.drugs.map((d) => d.name.toLowerCase()));
        const toAdd = items.filter((item) => !existing.has(item.ten_thuoc.toLowerCase())).map((item) => ({ name: item.ten_thuoc, known: true }));
        return toAdd.length ? { ...p, drugs: [...p.drugs, ...toAdd] } : p;
      }));
      setResult(null);
    } catch { /* import lỗi âm thầm bỏ qua, người dùng vẫn có thể nhập tay */ }
  }

  function resetAll() {
    if (!window.confirm("Xóa toàn bộ đơn thuốc, thuốc đã nhập và kết quả tra cứu hiện tại?")) return;
    setPrescriptions([createPrescription(1)]);
    setResult(null);
    setResultPrescriptions(null);
    setError(null);
    setQuery("");
    setSuggestions([]);
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

    {!boardMode && <form className="interaction-search panel" onSubmit={(e) => { e.preventDefault(); if (query.trim() && suggestions.length === 0) addDrug(query.trim(), false); else void runCheck(e); }}><label htmlFor="interaction-search">Tìm kiếm thuốc</label><div className="interaction-search__input"><MaterialIcon name="search" size={21} /><input id="interaction-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập tên thuốc, ví dụ Panadol" autoComplete="off" />{query && <button type="button" onClick={() => { setQuery(""); setSuggestions([]); }} aria-label="Xóa tìm kiếm"><MaterialIcon name="close" size={18} /></button>}</div>{suggestions.length > 0 ? <ul className="interaction-suggestions">{suggestions.slice(0, 5).map((item) => <li key={item.id} onClick={() => addDrug(item.ten_thuoc)}><div><strong>{item.ten_thuoc}</strong><small>Thuốc trong cơ sở dữ liệu</small></div><MaterialIcon name="add_circle_outline" size={21} /></li>)}</ul> : query.trim().length >= 2 && <button type="button" className="interaction-unknown" onClick={() => addDrug(query.trim(), false)}><div><strong>Không tìm thấy "{query.trim()}"</strong><small>Thêm thuốc chưa cập nhật trong cơ sở dữ liệu</small></div><MaterialIcon name="add_circle_outline" size={21} /></button>}</form>}

    {error && <p className="error-text" role="alert">{error}</p>}
    {result && ((result.unknown_products?.length ?? 0) > 0 || (result.no_interaction_data_products?.length ?? 0) > 0) && <div className="guest-mode-banner"><MaterialIcon name="info" size={18} /><span>{result.unknown_products && result.unknown_products.length > 0 && `Không tìm thấy trong CSDL: ${result.unknown_products.join(", ")}. `}{result.no_interaction_data_products && result.no_interaction_data_products.length > 0 && `Chưa có dữ liệu hoạt chất để kiểm tra tương tác: ${result.no_interaction_data_products.join(", ")}.`}</span></div>}

    {boardMode && <section className="prescription-board-wrap">
      <div className="prescription-board">
        {prescriptions.map((p) => (
          <PrescriptionPanel key={p.id} label={p.label} drugs={p.drugs} search={searchFn}
            onAdd={(name, known) => addDrugTo(p.id, name, known)}
            onRemoveDrug={(name) => removeDrugFrom(p.id, name)}
            onRemovePanel={() => removePrescription(p.id)}
            onImport={session ? () => importFromProfile(p.id) : undefined}
            inputId={`prescription-search-${p.id}`} />
        ))}
        <button type="button" className="prescription-board__add" onClick={addPrescription}>
          <MaterialIcon name="add_circle" size={26} /><span>Thêm đơn thuốc</span>
        </button>
      </div>
      <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || mergedDrugNames(prescriptions).length < 2}>
        <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
      </button>
    </section>}

    {!boardMode && <div className="interaction-workspace interaction-workspace--board">
      <aside className="interaction-selection panel"><div className="interaction-selection__header"><h2>Thuốc đang chọn</h2><span>{primary.drugs.length}</span></div>{session && <button type="button" className="prescription-panel__tool interaction-selection__import" onClick={() => void importFromProfile(primary.id)}><MaterialIcon name="download" size={16} /><span>Nhập từ hồ sơ</span></button>}{primary.drugs.length === 0 && <div className="interaction-selection__empty"><MaterialIcon name="medication" size={34} /><p>Chọn thuốc ở ô tìm kiếm phía trên để bắt đầu.</p></div>}{primary.drugs.map((item, index) => <div className={`selected-medication ${!item.known ? "selected-medication--unknown" : ""}`} key={item.name}><span className="selected-medication__icon"><MaterialIcon name="medication" size={21} /></span><div><strong>{item.name}</strong><small>{item.known ? (index === 0 ? "Thuốc hiện tại" : "Thuốc mới thêm") : "Chưa cập nhật trong cơ sở dữ liệu"}</small></div><button type="button" onClick={() => removeDrugFrom(primary.id, item.name)} aria-label={`Xóa ${item.name}`}><MaterialIcon name="close" size={19} /></button></div>)}<button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || primary.drugs.length < 2}><MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}</button><button type="button" className="prescription-add-link" onClick={addPrescription}><MaterialIcon name="add_circle_outline" size={17} /> Thêm đơn thuốc để so sánh nhiều đơn</button></aside>
    </div>}

    {result && <InteractionResultView result={result} prescriptions={resultPrescriptions ?? []} session={session} />}
  </main>;
}

export default function InteractionPage() {
  return <Suspense fallback={<main className="interaction-page"><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}><InteractionPageContent /></Suspense>;
}
