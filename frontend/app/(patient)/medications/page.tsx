"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, addPatientMedication, searchProducts, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";

export default function MedicationsPage() {
  const router = useRouter();
  const session = getSession();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!session || query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => searchProducts(query.trim(), session.accessToken).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function handleSave(name: string) {
    if (!session) return;
    setSaving(true); setError(null);
    try { await addPatientMedication(session.userId, name, session.accessToken); router.push("/dashboard"); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không thêm được thuốc"); }
    finally { setSaving(false); }
  }

  function submit(e: FormEvent) { e.preventDefault(); if (query.trim()) void handleSave(query.trim()); }
  if (!session) return null;

  return (
    <main>
      <div className="page-header page-header--in-content"><button className="page-header__back" onClick={() => router.back()} aria-label="Quay lại"><MaterialIcon name="arrow_back" size={22} /></button><div><p className="eyebrow">HỒ SƠ THUỐC</p><h1 className="page-header__title">Thêm thuốc</h1></div></div>
      <section className="intro-panel"><div className="intro-panel__icon"><MaterialIcon name="medication" size={28} /></div><div><h2>Thêm thuốc bạn đang sử dụng</h2><p>Tìm theo tên thuốc (biệt dược) để lưu vào hồ sơ.</p></div></section>
      <form className="panel medication-form" onSubmit={submit}>
        <div className="field autocomplete"><label htmlFor="medication_name">Tên thuốc</label><div className="search-bar__field"><MaterialIcon name="search" size={20} className="search-bar__icon" /><input id="medication_name" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ví dụ: Panadol, Aspirin DWP..." autoComplete="off" required /></div>
          {suggestions.length > 0 && <ul className="autocomplete-list">{suggestions.map((s) => <li key={s.id} onClick={() => { setQuery(s.ten_thuoc); setSuggestions([]); }}>{s.ten_thuoc}</li>)}</ul>}
        </div>
        {error && <p className="error-text" role="alert">{error}</p>}
        <button type="submit" className="btn-block" disabled={saving || !query.trim()}>{saving ? <><span className="spinner spinner--sm" /> Đang lưu...</> : <><MaterialIcon name="save" size={20} /> Lưu vào hồ sơ</>}</button>
      </form>
      <div className="notice-box"><MaterialIcon name="info" size={20} /><span>Chỉ thêm thuốc theo hướng dẫn của bác sĩ hoặc dược sĩ. Bạn có thể xóa thuốc bất kỳ lúc nào trong hồ sơ.</span></div>
    </main>
  );
}
