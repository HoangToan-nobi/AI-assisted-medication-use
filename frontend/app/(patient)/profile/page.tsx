"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, addPatientMedication, listPatientMedications, removePatientMedication, searchMedications, type MedicationItem, type MedicationSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";

export default function ProfilePage() {
  const router = useRouter();
  const session = getSession();
  const [medications, setMedications] = useState<MedicationItem[]>([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<MedicationSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    listPatientMedications(session.userId, session.accessToken).then(setMedications).catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được hồ sơ thuốc")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!session || query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => searchMedications(query.trim(), session.accessToken).then(setSuggestions).catch(() => setSuggestions([])), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function addDrug(e?: FormEvent) {
    e?.preventDefault();
    if (!session || !query.trim()) return;
    setSaving(true); setError(null);
    try { const item = await addPatientMedication(session.userId, query.trim(), session.accessToken); setMedications((items) => [...items, item]); setQuery(""); setSuggestions([]); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không thể thêm thuốc vào hồ sơ"); }
    finally { setSaving(false); }
  }
  async function deleteDrug(id: string) {
    if (!session) return;
    setDeleting(id); setError(null);
    try { await removePatientMedication(session.userId, id, session.accessToken); setMedications((items) => items.filter((item) => item.id !== id)); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Không thể xóa thuốc"); }
    finally { setDeleting(null); }
  }
  if (!session) return null;
  return <main className="profile-page"><div className="page-header page-header--in-content"><button className="page-header__back" onClick={() => router.back()} aria-label="Quay lại"><MaterialIcon name="arrow_back" size={22} /></button><div><p className="eyebrow">HỒ SƠ CỦA TÔI</p><h1 className="page-header__title">Đơn thuốc hiện tại</h1></div></div><section className="profile-intro"><div className="profile-avatar"><MaterialIcon name="person" size={26} /></div><div><h2>{session.hoTen}</h2><p>Quản lý các thuốc đang sử dụng để kiểm tra tương tác chính xác hơn.</p></div></section><form className="panel profile-add-form" onSubmit={addDrug}><label htmlFor="profile-medication">Thêm thuốc vào đơn hiện tại</label><div className="profile-add-form__input"><MaterialIcon name="search" size={20} /><input id="profile-medication" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập tên thuốc hoặc hoạt chất" autoComplete="off" /><button type="submit" disabled={saving || !query.trim()}>{saving ? <span className="spinner spinner--sm" /> : <MaterialIcon name="add" size={20} />} Thêm</button></div>{suggestions.length > 0 && <ul className="autocomplete-list profile-suggestions">{suggestions.map((item) => <li key={item.id} onClick={() => { setQuery(item.ten_chuan_hoa); setSuggestions([]); }}>{item.ten_chuan_hoa}</li>)}</ul>}</form>{error && <p className="error-text" role="alert">{error}</p>}<section className="profile-medications"><div className="dashboard-section__header"><h2>Thuốc trong đơn ({medications.length})</h2><button className="secondary" onClick={() => router.push("/interaction")}><MaterialIcon name="hub" size={18} /> Kiểm tra tương tác</button></div>{loading && <div className="loading-row"><span className="spinner" /> Đang tải...</div>}{!loading && medications.length === 0 && <div className="empty-state"><MaterialIcon name="medication" size={40} /><strong>Chưa có thuốc trong hồ sơ</strong><span>Thêm thuốc để hệ thống có thể đối chiếu tương tác.</span></div>}{medications.map((item) => <article className="profile-medication" key={item.id} onClick={() => router.push(`/medications/${item.id}`)}><span className="profile-medication__icon"><MaterialIcon name="medication" size={22} /></span><div><strong>{item.ten_chuan_hoa}</strong><p>{item.ngay_bat_dau ? `Bắt đầu từ ${item.ngay_bat_dau}` : "Được thêm hôm nay"}</p></div><button className="icon-btn" onClick={(event) => { event.stopPropagation(); void deleteDrug(item.id); }} disabled={deleting === item.id} aria-label={`Xóa ${item.ten_chuan_hoa}`}>{deleting === item.id ? <span className="spinner spinner--sm" /> : <MaterialIcon name="delete_outline" size={20} />}</button></article>)}</section></main>;
}
