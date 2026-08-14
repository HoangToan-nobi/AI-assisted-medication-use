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
  listPatientNotifications,
  listPatientPrescriptions,
  markNotificationRead,
  removePatientMedication,
  type InteractionCheckSummary,
  type NotificationItem,
  type PatientPrescription,
} from "@/lib/api";
import { getSession } from "@/lib/auth";
import { formatVietnameseDateTime } from "@/lib/datetime";

export default function PatientDashboardPage() {
  const router = useRouter();
  const session = getSession();
  const [prescriptions, setPrescriptions] = useState<PatientPrescription[]>([]);
  const [history, setHistory] = useState<InteractionCheckSummary[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    Promise.all([
      listPatientPrescriptions(session.userId, session.accessToken),
      listPatientChecks(session.userId, session.accessToken),
      listPatientNotifications(session.userId, session.accessToken),
    ])
      .then(([saved, checks, notifs]) => { setPrescriptions(saved); setHistory(checks); setNotifications(notifs); })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleOpenNotification(n: NotificationItem) {
    if (!session) return;
    try { await markNotificationRead(session.userId, n.id, session.accessToken); } catch { /* điều hướng dù lỗi mark-read, không chặn người dùng */ }
    if (n.interaction_check_id) router.push(`/check-result?checkId=${n.interaction_check_id}`);
  }

  const totalMedications = prescriptions.reduce((sum, p) => sum + p.medications.length, 0);

  async function handleCheck() {
    if (!session) return;
    if (totalMedications < 2) { setError("Cần ít nhất 2 loại thuốc trong hồ sơ để kiểm tra tương tác."); return; }
    setChecking(true); setError(null);
    try {
      const result = await checkProducts(
        prescriptions
          .filter((p) => p.medications.length > 0)
          .map((p) => ({ label: p.label, products: p.medications.map((m) => m.ten_thuoc) })),
        session.accessToken
      );
      window.sessionStorage.setItem("medguard_last_check", JSON.stringify(result));
      router.push("/check-result");
    } catch (err) { setError(err instanceof ApiError ? err.message : "Kiểm tra tương tác thất bại"); }
    finally { setChecking(false); }
  }

  async function handleDelete(prescriptionId: string, medicationId: string) {
    if (!session || !window.confirm("Xóa thuốc này khỏi hồ sơ?")) return;
    setDeletingId(medicationId); setError(null);
    try {
      await removePatientMedication(session.userId, medicationId, session.accessToken);
      setPrescriptions((prev) => prev.map((p) => (p.id === prescriptionId ? { ...p, medications: p.medications.filter((m) => m.id !== medicationId) } : p)));
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

      {notifications.filter((n) => !n.da_doc).length > 0 && (
        <section className="dashboard-notifications">
          {notifications.filter((n) => !n.da_doc).slice(0, 3).map((n) => (
            <button type="button" className="dashboard-notification" key={n.id} onClick={() => void handleOpenNotification(n)}>
              <MaterialIcon name="notifications" size={20} />
              <span>{n.noi_dung}</span>
              <MaterialIcon name="chevron_right" size={18} />
            </button>
          ))}
        </section>
      )}

      <section className="dashboard-section">
        <div className="dashboard-section__header"><h2>Đơn thuốc của tôi</h2><Link href="/profile?tab=prescriptions">Xem tất cả <MaterialIcon name="arrow_forward" size={17} /></Link></div>
        {!loading && totalMedications === 0 && <div className="empty-state"><MaterialIcon name="medication" size={40} /><strong>Chưa có thuốc trong hồ sơ</strong><span>Thêm thuốc để bắt đầu kiểm tra tương tác.</span></div>}
        {totalMedications > 0 && (
          <div className="prescription-board prescription-board--slider">
            {prescriptions.filter((p) => p.medications.length > 0).map((p) => (
              <div className="prescription-panel panel prescription-panel--readonly" key={p.id}>
                <div className="prescription-panel__header">
                  <h3>{p.label}</h3>
                </div>
                <div className="prescription-panel__list">
                  {p.medications.map((m) => (
                    <div className="selected-medication" key={m.id}>
                      <span className="selected-medication__icon"><MaterialIcon name="medication" size={18} /></span>
                      <div><strong>{m.ten_thuoc}</strong><small>{m.ngay_bat_dau ? `Bắt đầu từ ${m.ngay_bat_dau}` : "Được thêm hôm nay"}</small></div>
                      <button type="button" onClick={() => handleDelete(p.id, m.id)} disabled={deletingId === m.id} aria-label={`Xóa ${m.ten_thuoc}`}>
                        {deletingId === m.id ? <span className="spinner spinner--sm" /> : <MaterialIcon name="close" size={17} />}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="dashboard-summary-row"><div><span className="dashboard-summary-number">{totalMedications}</span><span> thuốc đang theo dõi</span></div><div><span className="dashboard-summary-number">{unresolvedSevere}</span><span> cảnh báo chưa xử lý</span></div></section>
      <Disclaimer />

      {history.length > 0 && <section className="dashboard-history"><div className="dashboard-section__header"><h2>Lịch sử kiểm tra gần đây</h2><Link href="/history">Xem tất cả <MaterialIcon name="arrow_forward" size={17} /></Link></div>{history.slice(0, 3).map((h) => <button className="history-card" key={h.id} onClick={() => router.push(`/check-result?checkId=${h.id}`)}><span>{formatVietnameseDateTime(h.thoi_gian_kiem_tra)}</span><strong>{h.co_canh_bao_nang ? "Có cảnh báo cần chú ý" : "Chưa phát hiện cảnh báo nghiêm trọng"}</strong><MaterialIcon name="chevron_right" size={20} /></button>)}</section>}

      {!loading && totalMedications >= 2 && (
        <button className="interaction-run" type="button" onClick={() => void handleCheck()} disabled={checking} style={{ marginTop: "16px" }}>
          <MaterialIcon name="analytics" size={19} />{checking ? "Đang phân tích..." : "Kiểm tra tương tác"}
        </button>
      )}
    </main>
  );
}
