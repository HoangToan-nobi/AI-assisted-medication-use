"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, listPharmacistPatients, type PatientSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { getInitials } from "@/lib/format";

export default function PharmacistPatientsPage() {
  const router = useRouter();
  const session = getSession();

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) return;
    listPharmacistPatients(session.userId, session.accessToken)
      .then(setPatients)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được danh sách người dùng")
      )
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!session) return null;

  const urgentCount = patients.filter((p) => p.co_canh_bao_nang_chua_xu_ly).length;

  return (
    <main>
      <h1>Người dùng phụ trách</h1>

      {!loading && patients.length > 0 && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{patients.length}</div>
            <div className="stat-label">Tổng người dùng</div>
          </div>
          <div className={`stat-card ${urgentCount > 0 ? "attention" : ""}`}>
            <div className="stat-value">{urgentCount}</div>
            <div className="stat-label">Cần xử lý gấp</div>
          </div>
        </div>
      )}

      {loading && (
        <div className="loading-row">
          <span className="spinner" aria-hidden="true" />
          Đang tải danh sách...
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
      {!loading && patients.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            🗂️
          </span>
          Chưa có người dùng nào được phân công cho bạn.
        </div>
      )}

      <ul>
        {patients.map((p) => (
          <li key={p.id} className="card hoverable">
            <div className="actions-row" style={{ margin: 0, justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="avatar">{getInitials(p.ho_ten)}</span>
                <strong>{p.ho_ten}</strong>
              </div>
              {p.co_canh_bao_nang_chua_xu_ly ? (
                <span className="badge badge-urgent">🚨 Cần xử lý gấp</span>
              ) : (
                <span className="badge badge-ok">Ổn định</span>
              )}
            </div>
            <div style={{ marginTop: 12 }}>
              <button
                className="secondary"
                onClick={() => router.push(`/review?patientId=${p.id}`)}
              >
                Xem chi tiết →
              </button>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
