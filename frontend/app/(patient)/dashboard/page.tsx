"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import {
  ApiError,
  checkProducts,
  listPatientChecks,
  listPatientMedications,
  removePatientMedication,
  type InteractionCheckSummary,
  type MedicationItem,
} from "@/lib/api";
import { getSession } from "@/lib/auth";
import { formatVietnameseDateTime } from "@/lib/datetime";

export default function PatientDashboardPage() {
  const router = useRouter();
  const session = getSession();
  const [medications, setMedications] = useState<MedicationItem[]>([]);
  const [history, setHistory] = useState<InteractionCheckSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    Promise.all([
      listPatientMedications(session.userId, session.accessToken),
      listPatientChecks(session.userId, session.accessToken),
    ])
      .then(([meds, checks]) => { setMedications(meds); setHistory(checks); })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCheck() {
    if (!session) return;
    if (medications.length < 2) { setError("Cần ít nhất 2 loại thuốc trong hồ sơ để kiểm tra tương tác."); return; }
    setChecking(true); setError(null);
    try {
      const result = await checkProducts(
        [{ label: "Thuốc hiện tại", products: medications.map((m) => m.ten_thuoc) }],
        session.accessToken
      );
      window.sessionStorage.setItem("medguard_last_check", JSON.stringify(result));
      router.push("/check-result");
    } catch (err) { setError(err instanceof ApiError ? err.message : "Kiểm tra tương tác thất bại"); }
    finally { setChecking(false); }
  }

  async function handleDelete(id: string) {
    if (!session || !window.confirm("Xóa thuốc này khỏi hồ sơ?")) return;
    setDeletingId(id); setError(null);
    try {
      await removePatientMedication(session.userId, id, session.accessToken);
      setMedications((prev) => prev.filter((m) => m.id !== id));
    } catch (err) { setError(err instanceof ApiError ? err.message : "Không xóa được thuốc"); }
    finally { setDeletingId(null); }
  }

  if (!session) return null;
  const unresolvedSevere = history.filter((h) => h.co_canh_bao_nang && h.trang_thai_xac_nhan !== "da_xac_nhan").length;
  const firstName = session.hoTen.split(" ").pop() || session.hoTen;

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero" style={{ background: "linear-gradient(to right, #ffe1cc 0%, #d2e3fc 100%)", padding: "32px", borderRadius: "12px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 className="dashboard-title" style={{ margin: 0, fontSize: "28px", color: "#1a2b4c" }}>Xin chào, {firstName}</h1>
          <p style={{ marginTop: "8px", color: "#4a5b7c", fontSize: "15px" }}>Tóm tắt sức khỏe hôm nay của bạn có vẻ rất tốt.</p>
        </div>

      </section>

      {loading && <div className="loading-row"><span className="spinner" /> Đang tải hồ sơ...</div>}
      {error && <p className="error-text" role="alert">{error}</p>}

      <section className="dashboard-section">
        <div className="dashboard-section__header"><h2>Thuốc của tôi</h2><Link href="/medications">Xem tất cả <MaterialIcon name="arrow_forward" size={17} /></Link></div>
        {!loading && medications.length === 0 && <div className="empty-state"><MaterialIcon name="medication" size={40} /><strong>Chưa có thuốc trong hồ sơ</strong><span>Thêm thuốc để bắt đầu kiểm tra tương tác.</span></div>}
        <div className="dashboard-med-grid">
          {medications.map((m) => (
            <article className="dashboard-med-card" key={m.id}>
              <div className="dashboard-med-card__top"><h3>{m.ten_thuoc}</h3><span className={`med-status ${m.ngay_bat_dau ? "med-status--confirmed" : "med-status--pending"}`}>{m.ngay_bat_dau ? "Đã xác nhận" : "Chưa xác nhận"}</span></div>
              <p className="dashboard-med-card__instruction">{m.ngay_bat_dau ? "Đang được theo dõi trong hồ sơ thuốc." : "Được thêm bởi bệnh nhân hôm nay."}</p>
              <div className="dashboard-med-card__footer"><span><MaterialIcon name="calendar_today" size={17} />{m.ngay_bat_dau ? `Bắt đầu: ${m.ngay_bat_dau}` : "Cập nhật hôm nay"}</span><button className="med-delete" onClick={() => handleDelete(m.id)} disabled={deletingId === m.id} aria-label={`Xóa ${m.ten_thuoc}`}>{deletingId === m.id ? <span className="spinner spinner--sm" /> : <MaterialIcon name="more_horiz" size={20} />}</button></div>
            </article>
          ))}
        </div>
      </section>

      <section className="dashboard-summary-row"><div><span className="dashboard-summary-number">{medications.length}</span><span> thuốc đang theo dõi</span></div><div><span className="dashboard-summary-number">{unresolvedSevere}</span><span> cảnh báo chưa xử lý</span></div></section>
      <Disclaimer />

      {history.length > 0 && <section className="dashboard-history"><div className="dashboard-section__header"><h2>Lịch sử kiểm tra gần đây</h2><Link href="/check-result">Xem tất cả <MaterialIcon name="arrow_forward" size={17} /></Link></div>{history.slice(0, 3).map((h) => <button className="history-card" key={h.id} onClick={() => router.push(`/check-result?checkId=${h.id}`)}><span>{formatVietnameseDateTime(h.thoi_gian_kiem_tra)}</span><strong>{h.co_canh_bao_nang ? "Có cảnh báo cần chú ý" : "Chưa phát hiện cảnh báo nghiêm trọng"}</strong><MaterialIcon name="chevron_right" size={20} /></button>)}</section>}
    </main>
  );
}
