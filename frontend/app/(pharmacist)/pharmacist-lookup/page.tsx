"use client";

import { useEffect, useState, type FormEvent } from "react";
import MaterialIcon from "@/components/MaterialIcon";
import AlertCard from "@/components/AlertCard";
import { ApiError, checkProductsAsPharmacist, searchProducts, type MedicationCheckResponse, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";

type SelectedDrug = { name: string; known: boolean };

export default function PharmacistLookupPage() {
  const session = getSession();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [selected, setSelected] = useState<SelectedDrug[]>([]);
  const [result, setResult] = useState<MedicationCheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session || query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => searchProducts(query.trim(), session.accessToken).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  function addDrug(name: string, known = true) {
    if (!selected.some((item) => item.name.toLowerCase() === name.toLowerCase())) setSelected((items) => [...items, { name, known }]);
    setQuery(""); setSuggestions([]); setResult(null);
  }

  function removeDrug(name: string) {
    setSelected((items) => items.filter((item) => item.name !== name));
    setResult(null);
  }

  async function runCheck(e?: FormEvent) {
    e?.preventDefault();
    if (!session) return;
    if (selected.length < 2) { setError("Hãy chọn ít nhất 2 thuốc để phân tích tương tác."); return; }
    setError(null); setLoading(true);
    try {
      const data = await checkProductsAsPharmacist(selected.map((item) => item.name), session.accessToken);
      setResult(data);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Không thể phân tích tương tác lúc này."); }
    finally { setLoading(false); }
  }

  if (!session) return null;

  return (
    <main>
      <section className="greeting">
        <p className="eyebrow">SỔ TAY DƯỢC SĨ</p>
        <h1 className="greeting__title">Tra cứu tương tác thuốc</h1>
        <p className="greeting__subtitle">Công cụ tra cứu nội bộ — không lưu lịch sử, không gắn với bệnh nhân nào.</p>
      </section>

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
            <div><strong>Không tìm thấy “{query.trim()}”</strong><small>Thêm thuốc chưa cập nhật trong cơ sở dữ liệu</small></div>
            <MaterialIcon name="add_circle_outline" size={21} />
          </button>
        )}
      </form>
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

      <section className="panel interaction-selection">
        <div className="interaction-selection__header"><h2>Thuốc đang chọn</h2><span>{selected.length}</span></div>
        {selected.length === 0 && (
          <div className="interaction-selection__empty">
            <MaterialIcon name="medication" size={34} />
            <p>Chọn thuốc ở ô tìm kiếm phía trên để bắt đầu.</p>
          </div>
        )}
        {selected.map((item) => (
          <div className={`selected-medication ${!item.known ? "selected-medication--unknown" : ""}`} key={item.name}>
            <span className="selected-medication__icon"><MaterialIcon name="medication" size={21} /></span>
            <div><strong>{item.name}</strong><small>{item.known ? "Thuốc trong cơ sở dữ liệu" : "Chưa cập nhật trong cơ sở dữ liệu"}</small></div>
            <button type="button" onClick={() => removeDrug(item.name)} aria-label={`Xóa ${item.name}`}><MaterialIcon name="close" size={19} /></button>
          </div>
        ))}
        <button className="interaction-run" type="button" onClick={() => void runCheck()} disabled={loading || selected.length < 2}>
          <MaterialIcon name="analytics" size={19} />{loading ? "Đang phân tích..." : "Phân tích tương tác"}
        </button>
      </section>

      {result && (
        <section className="interaction-pairs">
          <div className="dashboard-section__header">
            <h2><MaterialIcon name="fact_check" size={21} /> Kết quả phân tích</h2>
            <span>{result.explanations.length} cặp tương tác</span>
          </div>
          {result.explanations.length === 0 && (
            <div className="empty-state">
              <MaterialIcon name="check_circle" size={40} />
              <strong>Không phát hiện tương tác</strong>
              <span>Chưa ghi nhận tương tác nào giữa các thuốc đã chọn.</span>
            </div>
          )}
          {result.explanations.map((item, index) => (
            <div className="interaction-pair-card" key={`${item.thuoc_a}-${item.thuoc_b}-${index}`}>
              <AlertCard thuocA={item.thuoc_a} thuocB={item.thuoc_b} severity={item.muc_do} description={item.giai_thich} source={item.nguon_trich_dan} management={item.xu_tri} />
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
