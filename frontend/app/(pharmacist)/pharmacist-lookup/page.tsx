"use client";

import { useEffect, useState, type FormEvent } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import AlertCard from "@/components/AlertCard";
import PrescriptionPanel from "@/components/PrescriptionPanel";
import { ApiError, checkProductsAsPharmacist, searchProducts, type MedicationCheckResponse, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { createPrescription, drugOrigins, isCrossPrescription, mergedDrugNames, nonEmptyPrescriptions, originLabel, toPrescriptionCheckInput, type Prescription } from "@/lib/prescription";

export default function PharmacistLookupPage() {
  const session = getSession();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(() => [createPrescription(1)]);
  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllPairs, setShowAllPairs] = useState(false);

  const boardMode = prescriptions.length > 1;
  const primary = prescriptions[0];

  useEffect(() => {
    if (!session || query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => searchProducts(query.trim(), session.accessToken).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const searchFn = (q: string) => (session ? searchProducts(q, session.accessToken) : Promise.resolve([]));

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

  async function runCheck(e?: FormEvent) {
    e?.preventDefault();
    if (!session) return;
    const activePrescriptions = nonEmptyPrescriptions(prescriptions);
    if (mergedDrugNames(activePrescriptions).length < 2) { setError("Hãy chọn ít nhất 2 thuốc để phân tích tương tác."); return; }
    setError(null); setLoading(true);
    try {
      const data = await checkProductsAsPharmacist(toPrescriptionCheckInput(activePrescriptions), session.accessToken);
      setResult(data);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Không thể phân tích tương tác lúc này."); }
    finally { setLoading(false); }
  }

  if (!session) return null;

  const origins = drugOrigins(prescriptions);
  const explanationsAll = result?.explanations ?? [];
  const explanations = boardMode && !showAllPairs ? explanationsAll.filter((item) => isCrossPrescription(origins, item.thuoc_a, item.thuoc_b)) : explanationsAll;
  const crossCount = explanationsAll.filter((item) => isCrossPrescription(origins, item.thuoc_a, item.thuoc_b)).length;

  return (
    <main>
      <section className="greeting">
        <p className="eyebrow">SỔ TAY DƯỢC SĨ</p>
        <h1 className="greeting__title">Tra cứu tương tác thuốc</h1>
        <p className="greeting__subtitle">Công cụ tra cứu nội bộ — không lưu lịch sử, không gắn với bệnh nhân nào.</p>
      </section>

      {!boardMode && (
        <form className="interaction-search panel" onSubmit={(e) => { e.preventDefault(); if (query.trim() && suggestions.length === 0) addDrug(query.trim(), false); else void runCheck(e); }}>
          <label htmlFor="pharmacist-lookup-search">Tìm kiếm thuốc</label>
          <div className="interaction-search__input">
            <MaterialIcon name="search" size={21} />
            <input id="pharmacist-lookup-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập tên thuốc, ví dụ Panadol" autoComplete="off" />
            {query && <button type="button" onClick={() => { setQuery(""); setSuggestions([]); }} aria-label="Xóa tìm kiếm"><MaterialIcon name="close" size={18} /></button>}
          </div>
          {suggestions.length > 0 ? (
            <ul className="interaction-suggestions">
              {suggestions.slice(0, 5).map((item) => (
                <li key={item.id} onClick={() => addDrug(item.ten_thuoc)}>
                  <div><strong>{item.ten_thuoc}</strong><small>Thuốc trong cơ sở dữ liệu</small></div>
                  <MaterialIcon name="add_circle_outline" size={21} />
                </li>
              ))}
            </ul>
          ) : query.trim().length >= 2 && (
            <button type="button" className="interaction-unknown" onClick={() => addDrug(query.trim(), false)}>
              <div><strong>Không tìm thấy "{query.trim()}"</strong><small>Thêm thuốc chưa cập nhật trong cơ sở dữ liệu</small></div>
              <MaterialIcon name="add_circle_outline" size={21} />
            </button>
          )}
        </form>
      )}

      {error && <p className="error-text" role="alert">{error}</p>}
      {result && ((result.unknown_products?.length ?? 0) > 0 || (result.no_interaction_data_products?.length ?? 0) > 0) && (
        <div className="guest-mode-banner">
          <MaterialIcon name="info" size={18} />
          <span>
            {result.unknown_products && result.unknown_products.length > 0 && `Không tìm thấy trong CSDL: ${result.unknown_products.join(", ")}. `}
            {result.no_interaction_data_products && result.no_interaction_data_products.length > 0 && `Chưa có dữ liệu hoạt chất để kiểm tra tương tác: ${result.no_interaction_data_products.join(", ")}.`}
          </span>
        </div>
      )}

      {boardMode && (
        <section className="prescription-board-wrap">
          <div className="prescription-board">
            {prescriptions.map((p) => (
              <PrescriptionPanel key={p.id} label={p.label} drugs={p.drugs} search={searchFn}
                onAdd={(name, known) => addDrugTo(p.id, name, known)}
                onRemoveDrug={(name) => removeDrugFrom(p.id, name)}
                onRemovePanel={() => removePrescription(p.id)}
                inputId={`pharmacist-prescription-search-${p.id}`} />
            ))}
            <button type="button" className="prescription-board__add" onClick={addPrescription}>
              <MaterialIcon name="add_circle" size={26} /><span>Thêm đơn thuốc</span>
            </button>
          </div>
          <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || mergedDrugNames(prescriptions).length < 2}>
            <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
          </button>
        </section>
      )}

      {!boardMode && (
        <section className="panel interaction-selection">
          <div className="interaction-selection__header"><h2>Thuốc đang chọn</h2><span>{primary.drugs.length}</span></div>
          {primary.drugs.length === 0 && (
            <div className="interaction-selection__empty">
              <MaterialIcon name="medication" size={34} />
              <p>Chọn thuốc ở ô tìm kiếm phía trên để bắt đầu.</p>
            </div>
          )}
          {primary.drugs.map((item) => (
            <div className={`selected-medication ${!item.known ? "selected-medication--unknown" : ""}`} key={item.name}>
              <span className="selected-medication__icon"><MaterialIcon name="medication" size={21} /></span>
              <div><strong>{item.name}</strong><small>{item.known ? "Thuốc trong cơ sở dữ liệu" : "Chưa cập nhật trong cơ sở dữ liệu"}</small></div>
              <button type="button" onClick={() => removeDrugFrom(primary.id, item.name)} aria-label={`Xóa ${item.name}`}><MaterialIcon name="close" size={19} /></button>
            </div>
          ))}
          <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || primary.drugs.length < 2}>
            <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
          </button>
          <button type="button" className="prescription-add-link" onClick={addPrescription}><MaterialIcon name="add_circle_outline" size={17} /> Thêm đơn thuốc để so sánh nhiều đơn</button>
        </section>
      )}

      {result && (
        <section className="interaction-pairs">
          <div className="dashboard-section__header">
            <h2><MaterialIcon name="fact_check" size={21} /> Kết quả phân tích</h2>
            <span>{explanations.length} cặp tương tác</span>
          </div>
          {boardMode && explanationsAll.length > 0 && (
            <button type="button" className="interaction-pairs__toggle" onClick={() => setShowAllPairs((v) => !v)}>
              <MaterialIcon name={showAllPairs ? "visibility_off" : "visibility"} size={17} />
              {showAllPairs ? "Chỉ xem tương tác giữa các đơn" : `Xem tất cả tương tác (bao gồm trong cùng đơn) — còn ${explanationsAll.length - crossCount} cặp`}
            </button>
          )}
          {explanations.length === 0 && (
            <div className="empty-state">
              <MaterialIcon name="check_circle" size={40} />
              <strong>Không phát hiện tương tác</strong>
              <span>Chưa ghi nhận tương tác nào giữa các thuốc đã chọn.</span>
            </div>
          )}
          {explanations.map((item, index) => {
            const origin = boardMode ? originLabel(prescriptions, origins, item.thuoc_a, item.thuoc_b) : null;
            return (
              <div className="interaction-pair-card" key={`${item.thuoc_a}-${item.thuoc_b}-${index}`}>
                {origin && <span className="interaction-pair-card__origin">{origin}</span>}
                <AlertCard thuocA={item.thuoc_a} thuocB={item.thuoc_b} severity={item.muc_do} description={item.giai_thich_duoc_si ?? item.giai_thich} source={item.nguon_trich_dan} management={item.xu_tri} />
              </div>
            );
          })}
        </section>
      )}
    </main>
  );
}
