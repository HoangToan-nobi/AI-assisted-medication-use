"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import PatientPrescriptionPanel from "@/components/PatientPrescriptionPanel";
import {
  ApiError,
  addPatientMedication,
  createPatientPrescription,
  deletePatientPrescription,
  getPatientProfile,
  listPatientPrescriptions,
  removePatientMedication,
  renamePatientPrescription,
  searchProducts,
  updatePatientProfile,
  type MedicationItem,
  type PatientPrescription,
} from "@/lib/api";
import { getSession } from "@/lib/auth";

type ProfileTab = "personal" | "prescriptions";

function ProfilePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const session = getSession();
  const activeTab: ProfileTab = searchParams.get("tab") === "prescriptions" ? "prescriptions" : "personal";

  const [prescriptions, setPrescriptions] = useState<PatientPrescription[]>([]);
  const [prescriptionsLoading, setPrescriptionsLoading] = useState(true);
  const [prescriptionsError, setPrescriptionsError] = useState<string | null>(null);
  const [addingPrescription, setAddingPrescription] = useState(false);

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
    listPatientPrescriptions(session.userId, session.accessToken)
      .then(setPrescriptions)
      .catch((err) => setPrescriptionsError(err instanceof ApiError ? err.message : "Không tải được đơn thuốc"))
      .finally(() => setPrescriptionsLoading(false));
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

  const searchFn = (q: string) => searchProducts(q, session!.accessToken);

  async function handleAddDrug(prescriptionId: string, productName: string) {
    if (!session) return;
    const item = await addPatientMedication(session.userId, productName, session.accessToken, prescriptionId);
    setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, medications: [...p.medications, item] } : p)));
  }

  async function handleRemoveDrug(prescriptionId: string, medication: MedicationItem) {
    if (!session) return;
    await removePatientMedication(session.userId, medication.id, session.accessToken);
    setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, medications: p.medications.filter((m) => m.id !== medication.id) } : p)));
  }

  async function handleRename(prescriptionId: string, label: string) {
    if (!session) return;
    await renamePatientPrescription(session.userId, prescriptionId, label, session.accessToken);
    setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, label } : p)));
  }

  async function handleRemovePanel(prescriptionId: string) {
    if (!session) return;
    await deletePatientPrescription(session.userId, prescriptionId, session.accessToken);
    setPrescriptions((prev) => prev.filter((p) => p.id !== prescriptionId));
  }

  async function handleAddPrescription() {
    if (!session) return;
    setAddingPrescription(true); setPrescriptionsError(null);
    try {
      const created = await createPatientPrescription(session.userId, `Đơn thuốc ${prescriptions.length + 1}`, session.accessToken);
      setPrescriptions((prev) => [...prev, created]);
    } catch (err) { setPrescriptionsError(err instanceof ApiError ? err.message : "Không thể tạo đơn thuốc mới"); }
    finally { setAddingPrescription(false); }
  }

  if (!session) return null;

  return (
    <main className="profile-page">
      <div className="page-header page-header--in-content">
        <div>
          <p className="eyebrow">HỒ SƠ CỦA TÔI</p>
          <h1 className="page-header__title">{activeTab === "personal" ? "Thông tin cá nhân" : "Đơn thuốc của tôi"}</h1>
        </div>
      </div>

      <section className="profile-intro">
        <div className="profile-avatar"><MaterialIcon name="person" size={26} /></div>
        <div>
          <h2>{hoTen || session.hoTen}</h2>
          <p>
            {activeTab === "personal"
              ? "Xem và cập nhật thông tin cá nhân, tiền sử bệnh lý của bạn để hệ thống tư vấn chính xác hơn."
              : "Quản lý các đơn thuốc đang sử dụng — thêm, đổi tên hoặc xóa đơn để kiểm tra tương tác thuốc."}
          </p>
        </div>
        <span className="profile-intro__state"><MaterialIcon name="verified_user" size={18} /> Hồ sơ bảo mật</span>
      </section>

      {activeTab === "personal" && (
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
      )}

      {activeTab === "prescriptions" && (
        <section className="prescription-board-wrap">
          <div className="dashboard-section__header">
            <h2>Đơn thuốc của tôi ({prescriptions.length})</h2>
            <button className="secondary" onClick={() => router.push("/interaction?import=profile")}>
              <MaterialIcon name="hub" size={18} /> Kiểm tra tương tác
            </button>
          </div>
          {prescriptionsError && <p className="error-text" role="alert">{prescriptionsError}</p>}
          {prescriptionsLoading ? (
            <div className="panel"><div className="loading-row"><span className="spinner" /> Đang tải...</div></div>
          ) : (
            <div className="prescription-board prescription-board--slider">
              {prescriptions.map((p) => (
                <PatientPrescriptionPanel
                  key={p.id}
                  prescription={p}
                  canRemove={prescriptions.length > 1}
                  search={searchFn}
                  onAddDrug={(name) => handleAddDrug(p.id, name)}
                  onRemoveDrug={(med) => handleRemoveDrug(p.id, med)}
                  onRename={(label) => handleRename(p.id, label)}
                  onRemovePanel={() => handleRemovePanel(p.id)}
                  inputId={`patient-prescription-search-${p.id}`}
                />
              ))}
              <button type="button" className="prescription-board__add" onClick={() => void handleAddPrescription()} disabled={addingPrescription}>
                {addingPrescription ? <span className="spinner spinner--sm" /> : <MaterialIcon name="add_circle" size={26} />}
                <span>Thêm đơn thuốc</span>
              </button>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

export default function ProfilePage() {
  return <Suspense fallback={<main className="profile-page"><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}><ProfilePageContent /></Suspense>;
}
