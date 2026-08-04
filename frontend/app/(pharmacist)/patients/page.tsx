"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, listPharmacistPatients, type PatientSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";

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
        setError(err instanceof ApiError ? err.message : "Không tải được danh sách bệnh nhân")
      )
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!session) return null;

  return (
    <main>
      <h1>Bệnh nhân phụ trách</h1>
      {loading && <p>Đang tải...</p>}
      {error && <p className="error-text">{error}</p>}
      {!loading && patients.length === 0 && <p>Chưa có bệnh nhân nào được phân công.</p>}

      <ul>
        {patients.map((p) => (
          <li key={p.id} className="card">
            <div className="actions-row" style={{ margin: 0, justifyContent: "space-between" }}>
              <strong>{p.ho_ten}</strong>
              {p.co_canh_bao_nang_chua_xu_ly ? (
                <span className="badge badge-urgent">Cần xử lý gấp</span>
              ) : (
                <span className="badge badge-ok">Ổn định</span>
              )}
            </div>
            <div style={{ marginTop: 10 }}>
              <button
                className="secondary"
                onClick={() => router.push(`/review?patientId=${p.id}`)}
              >
                Xem chi tiết
              </button>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
