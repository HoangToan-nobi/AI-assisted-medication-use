"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Disclaimer from "@/components/Disclaimer";
import {
  ApiError,
  checkMedications,
  listPatientChecks,
  listPatientMedications,
  removePatientMedication,
  type InteractionCheckSummary,
  type MedicationItem,
} from "@/lib/api";
import { getSession } from "@/lib/auth";

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
      .then(([meds, checks]) => {
        setMedications(meds);
        setHistory(checks);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCheck() {
    if (!session) return;
    if (medications.length < 2) {
      setError("Cần ít nhất 2 loại thuốc trong hồ sơ để kiểm tra tương tác.");
      return;
    }
    setChecking(true);
    setError(null);
    try {
      const result = await checkMedications(
        medications.map((m) => m.ten_chuan_hoa),
        session.accessToken
      );
      window.sessionStorage.setItem("medguard_last_check", JSON.stringify(result));
      router.push("/check-result");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kiểm tra tương tác thất bại");
    } finally {
      setChecking(false);
    }
  }

  async function handleDelete(patientMedicationId: string) {
    if (!session) return;
    if (!window.confirm("Xóa thuốc này khỏi hồ sơ?")) return;

    setDeletingId(patientMedicationId);
    setError(null);
    try {
      await removePatientMedication(session.userId, patientMedicationId, session.accessToken);
      setMedications((prev) => prev.filter((m) => m.id !== patientMedicationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xóa được thuốc");
    } finally {
      setDeletingId(null);
    }
  }

  if (!session) return null;

  const unresolvedSevere = history.filter(
    (h) => h.co_canh_bao_nang && h.trang_thai_xac_nhan !== "da_xac_nhan"
  ).length;

  return (
    <main>
      <h1>Chào {session.hoTen.split(" ").pop()} 👋</h1>

      {loading ? (
        <div className="loading-row">
          <span className="spinner" aria-hidden="true" />
          Đang tải hồ sơ...
        </div>
      ) : (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{medications.length}</div>
            <div className="stat-label">Thuốc đang dùng</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{history.length}</div>
            <div className="stat-label">Lần đã kiểm tra</div>
          </div>
          <div className={`stat-card ${unresolvedSevere > 0 ? "attention" : ""}`}>
            <div className="stat-value">{unresolvedSevere}</div>
            <div className="stat-label">Cảnh báo chờ dược sĩ</div>
          </div>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      <h2>Thuốc đang dùng</h2>
      {!loading && medications.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            💊
          </span>
          Bạn chưa có thuốc nào trong hồ sơ.
          <br />
          Bấm &quot;Thêm thuốc&quot; bên dưới để bắt đầu.
        </div>
      )}

      <ul>
        {medications.map((m) => (
          <li key={m.id} className="card">
            <div className="medication-row">
              <div>
                <div className="medication-name">{m.ten_chuan_hoa}</div>
                {m.ngay_bat_dau && (
                  <div className="medication-meta">Từ ngày {m.ngay_bat_dau}</div>
                )}
              </div>
              <button
                className="icon-btn"
                onClick={() => handleDelete(m.id)}
                disabled={deletingId === m.id}
                title="Xóa khỏi hồ sơ"
                aria-label="Xóa khỏi hồ sơ"
              >
                {deletingId === m.id ? <span className="spinner" /> : "🗑"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="actions-row">
        <Link className="btn secondary" href="/medications">
          + Thêm thuốc
        </Link>
        <button onClick={handleCheck} disabled={checking}>
          {checking && <span className="spinner" aria-hidden="true" />}
          {checking ? "Đang kiểm tra..." : "🔍 Kiểm tra tương tác"}
        </button>
      </div>

      <Disclaimer />

      <h2>Lịch sử kiểm tra gần đây</h2>
      {history.length === 0 ? (
        <p style={{ color: "var(--text-muted)" }}>Chưa có lần kiểm tra nào.</p>
      ) : (
        <ul>
          {history.map((h) => (
            <li key={h.id} className="card hoverable">
              <button
                className="secondary"
                style={{ width: "100%", justifyContent: "space-between" }}
                onClick={() => router.push(`/check-result?checkId=${h.id}`)}
              >
                <span>{new Date(h.thoi_gian_kiem_tra).toLocaleString("vi-VN")}</span>
                <span style={{ display: "flex", gap: 8 }}>
                  {h.co_canh_bao_nang && <span className="badge badge-urgent">Nghiêm trọng</span>}
                  <span
                    className={`badge ${
                      h.trang_thai_xac_nhan === "da_xac_nhan" ? "badge-success" : "badge-ok"
                    }`}
                  >
                    {h.trang_thai_xac_nhan === "da_xac_nhan" ? "Đã xác nhận" : "Chưa xác nhận"}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
