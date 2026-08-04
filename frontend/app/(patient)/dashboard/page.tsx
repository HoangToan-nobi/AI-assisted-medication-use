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

  return (
    <main>
      <h1>Thuốc đang dùng</h1>

      {loading && <p>Đang tải...</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && medications.length === 0 && (
        <p>Bạn chưa có thuốc nào trong hồ sơ. Bấm &quot;Thêm thuốc&quot; để bắt đầu.</p>
      )}

      <ul>
        {medications.map((m) => (
          <li key={m.id} className="card">
            <div className="actions-row" style={{ margin: 0, justifyContent: "space-between" }}>
              <span>
                {m.ten_chuan_hoa}
                {m.ngay_bat_dau && <> — từ {m.ngay_bat_dau}</>}
              </span>
              <button
                className="secondary"
                onClick={() => handleDelete(m.id)}
                disabled={deletingId === m.id}
              >
                {deletingId === m.id ? "Đang xóa..." : "Xóa"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="actions-row">
        <Link className="btn" href="/medications">
          Thêm thuốc
        </Link>
        <button onClick={handleCheck} disabled={checking}>
          {checking ? "Đang kiểm tra..." : "Kiểm tra tương tác"}
        </button>
      </div>

      <Disclaimer />

      <h2>Lịch sử kiểm tra gần đây</h2>
      {history.length === 0 && <p>Chưa có lần kiểm tra nào.</p>}
      <ul>
        {history.map((h) => (
          <li key={h.id} className="card">
            <div className="actions-row" style={{ margin: 0, alignItems: "center" }}>
              <button
                className="secondary"
                onClick={() => router.push(`/check-result?checkId=${h.id}`)}
              >
                {new Date(h.thoi_gian_kiem_tra).toLocaleString("vi-VN")}
              </button>
              {h.co_canh_bao_nang && <span className="badge badge-urgent">Nghiêm trọng</span>}
              <span className="badge badge-ok">
                {h.trang_thai_xac_nhan === "da_xac_nhan"
                  ? "Đã dược sĩ xác nhận"
                  : "Chưa xác nhận"}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
