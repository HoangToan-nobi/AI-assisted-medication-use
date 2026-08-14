"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, addPatientMedication, getPatientProfile, listPatientMedications, removePatientMedication, searchProducts, updatePatientProfile, type MedicationItem, type ProductSearchResult } from "@/lib/api";
import { getSession } from "@/lib/auth";

export default function ProfilePage() {
  const router = useRouter();
  const session = getSession();
  const [medications, setMedications] = useState<MedicationItem[]>([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProductSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [hoTen, setHoTen] = useState("");
  const [ngaySinh, setNgaySinh] = useState("");
  const [gioiTinh, setGioiTinh] = useState("");
  const [canNang, setCanNang] = useState("");
  const [chieuCao, setChieuCao] = useState("");
  const [benhNenGhiChu, setBenhNenGhiChu] = useState("");
  const [diUngThuoc, setDiUngThuoc] = useState("");
  const [tinhTrangKhac, setTinhTrangKhac] = useState("");

  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    listPatientMedications(session.userId, session.accessToken).then(setMedications).catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được hồ sơ thuốc")).finally(() => setLoading(false));
    getPatientProfile(session.userId, session.accessToken)
      .then((info) => { 
        setHoTen(info.ho_ten ?? session.hoTen ?? "");
        setNgaySinh(info.ngay_sinh ?? ""); 
        setGioiTinh(info.gioi_tinh ?? "");
        setCanNang(info.can_nang?.toString() ?? "");
        setChieuCao(info.chieu_cao?.toString() ?? "");
        setBenhNenGhiChu(info.benh_nen_ghi_chu ?? ""); 
        setDiUngThuoc(info.di_ung_thuoc ?? "");
        setTinhTrangKhac(info.tinh_trang_khac ?? "");
      })
      .catch((err) => setProfileError(err instanceof ApiError ? err.message : "Không tải được thông tin cá nhân"))
      .finally(() => setProfileLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveProfile(e?: FormEvent) {
    e?.preventDefault();
    if (!session) return;
    setProfileSaving(true); setProfileError(null); setProfileSaved(false);
    try {
      await updatePatientProfile(session.userId, { 
        ho_ten: hoTen || null,
        ngay_sinh: ngaySinh || null, 
        gioi_tinh: gioiTinh || null,
        can_nang: canNang ? parseFloat(canNang) : null,
        chieu_cao: chieuCao ? parseFloat(chieuCao) : null,
        benh_nen_ghi_chu: benhNenGhiChu || null,
        di_ung_thuoc: diUngThuoc || null,
        tinh_trang_khac: tinhTrangKhac || null
      }, session.accessToken);
      setProfileSaved(true);
      // Optional: Refresh session ho_ten here if needed
    } catch (err) { setProfileError(err instanceof ApiError ? err.message : "Không thể lưu thông tin cá nhân"); }
    finally { setProfileSaving(false); }
  }
  useEffect(() => {
    if (!session || query.trim().length < 2) { setSuggestions([]); return; }
    const timer = setTimeout(() => searchProducts(query.trim(), session.accessToken).then(setSuggestions).catch(() => setSuggestions([])), 250);
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
  
  return (
    <main className="profile-page">
      <div className="page-header page-header--in-content">
        <button className="page-header__back" onClick={() => router.back()} aria-label="Quay lại"><MaterialIcon name="arrow_back" size={22} /></button>
        <div>
          <p className="eyebrow">HỒ SƠ CỦA TÔI</p>
          <h1 className="page-header__title">Hồ sơ</h1>
        </div>
      </div>
      
      <section className="profile-intro">
        <div className="profile-avatar"><MaterialIcon name="person" size={26} /></div>
        <div>
          <h2>{hoTen || session.hoTen}</h2>
          <p>Quản lý thông tin cá nhân và các thuốc đang sử dụng để kiểm tra tương tác chính xác hơn.</p>
        </div>
      </section>

      <form onSubmit={saveProfile} style={{ display: "flex", flexDirection: "column", gap: "24px", marginBottom: "24px" }}>
        {profileLoading ? <div className="panel"><div className="loading-row"><span className="spinner" /> Đang tải...</div></div> : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", alignItems: "start" }}>
            {/* Cột 1: Thông tin cơ bản */}
            <div className="panel profile-add-form" style={{ height: "100%" }}>
              <h3 style={{ marginBottom: "16px", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                <MaterialIcon name="person" size={20} /> Thông tin cơ bản
              </h3>
              
              <div className="field">
                <label>Họ và tên</label>
                <input type="text" value={hoTen} onChange={(e) => setHoTen(e.target.value)} placeholder="Nhập họ và tên" />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="field">
                  <label>Ngày sinh</label>
                  <input type="date" value={ngaySinh} onChange={(e) => setNgaySinh(e.target.value)} />
                </div>
                <div className="field">
                  <label>Giới tính</label>
                  <select value={gioiTinh} onChange={(e) => setGioiTinh(e.target.value)} style={{ padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color)", backgroundColor: "var(--input-bg)", color: "var(--text-color)" }}>
                    <option value="">Chọn...</option>
                    <option value="Nam">Nam</option>
                    <option value="Nữ">Nữ</option>
                    <option value="Khác">Khác</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="field">
                  <label>Cân nặng (kg)</label>
                  <input type="number" step="0.1" value={canNang} onChange={(e) => setCanNang(e.target.value)} placeholder="Vd: 65" />
                </div>
                <div className="field">
                  <label>Chiều cao (cm)</label>
                  <input type="number" step="1" value={chieuCao} onChange={(e) => setChieuCao(e.target.value)} placeholder="Vd: 168" />
                </div>
              </div>
            </div>

            {/* Cột 2: Tiền sử y tế */}
            <div className="panel profile-add-form" style={{ height: "100%" }}>
              <h3 style={{ marginBottom: "16px", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px", display: "flex", alignItems: "center", gap: "8px", color: "var(--danger)" }}>
                <MaterialIcon name="medical_services" size={20} /> Tiền sử y tế
              </h3>

              <div className="field">
                <label>Bệnh lý nền</label>
                <textarea rows={2} value={benhNenGhiChu} onChange={(e) => setBenhNenGhiChu(e.target.value)} placeholder="Ví dụ: Tiểu đường type 2, cao huyết áp..." />
              </div>
              
              <div className="field">
                <label>Dị ứng thuốc</label>
                <textarea rows={2} value={diUngThuoc} onChange={(e) => setDiUngThuoc(e.target.value)} placeholder="Nhập chi tiết các loại thuốc gây dị ứng..." />
              </div>

              <div className="field">
                <label>Tình trạng mang thai hoặc trường hợp khác</label>
                <textarea rows={2} value={tinhTrangKhac} onChange={(e) => setTinhTrangKhac(e.target.value)} placeholder="Ghi chú thêm nếu đang mang thai, cho con bú..." />
              </div>
            </div>
            
            {/* Hành động */}
            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "16px" }}>
              {profileError && <p className="error-text" role="alert" style={{ margin: 0 }}>{profileError}</p>}
              {profileSaved && <p className="success-text" style={{ margin: 0 }}><MaterialIcon name="check_circle" size={18} /> Đã lưu thông tin</p>}
              <button type="submit" className="primary" disabled={profileSaving}>
                {profileSaving ? <span className="spinner spinner--sm" /> : <MaterialIcon name="save" size={20} />} Lưu thông tin
              </button>
            </div>
          </div>
        )}
      </form>

      <form className="panel profile-add-form" onSubmit={addDrug}><label htmlFor="profile-medication">Thêm thuốc vào đơn hiện tại</label><div className="profile-add-form__input"><MaterialIcon name="search" size={20} /><input id="profile-medication" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nhập tên thuốc (biệt dược)" autoComplete="off" /><button type="submit" disabled={saving || !query.trim()}>{saving ? <span className="spinner spinner--sm" /> : <MaterialIcon name="add" size={20} />} Thêm</button></div>{suggestions.length > 0 && <ul className="autocomplete-list profile-suggestions">{suggestions.map((item) => <li key={item.id} onClick={() => { setQuery(item.ten_thuoc); setSuggestions([]); }}>{item.ten_thuoc}</li>)}</ul>}</form>
      
      {error && <p className="error-text" role="alert">{error}</p>}
      
      <section className="profile-medications"><div className="dashboard-section__header"><h2>Thuốc trong đơn ({medications.length})</h2><button className="secondary" onClick={() => router.push("/interaction?import=profile")}><MaterialIcon name="hub" size={18} /> Kiểm tra tương tác</button></div>{loading && <div className="loading-row"><span className="spinner" /> Đang tải...</div>}{!loading && medications.length === 0 && <div className="empty-state"><MaterialIcon name="medication" size={40} /><strong>Chưa có thuốc trong hồ sơ</strong><span>Thêm thuốc để hệ thống có thể đối chiếu tương tác.</span></div>}{medications.map((item) => <article className="profile-medication" key={item.id} onClick={() => router.push(`/medications/${item.id}`)}><span className="profile-medication__icon"><MaterialIcon name="medication" size={22} /></span><div><strong>{item.ten_thuoc}</strong><p>{item.ngay_bat_dau ? `Bắt đầu từ ${item.ngay_bat_dau}` : "Được thêm hôm nay"}</p></div><button className="icon-btn" onClick={(event) => { event.stopPropagation(); void deleteDrug(item.id); }} disabled={deleting === item.id} aria-label={`Xóa ${item.ten_thuoc}`}>{deleting === item.id ? <span className="spinner spinner--sm" /> : <MaterialIcon name="delete_outline" size={20} />}</button></article>)}</section>
    </main>
  );
}
