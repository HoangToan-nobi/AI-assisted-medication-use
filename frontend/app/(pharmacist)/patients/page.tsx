"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
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
    listPharmacistPatients(session.userId, session.accessToken).then(setPatients).catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được danh sách bệnh nhân")).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!session) return null;
  const urgentCount = patients.filter((p) => p.co_canh_bao_nang_chua_xu_ly).length;

  return <main>
    <section className="greeting"><p className="eyebrow">TRUNG TÂM DƯỢC SĨ</p><h1 className="greeting__title">Bệnh nhân phụ trách</h1><p className="greeting__subtitle">Theo dõi các hồ sơ cần được xem xét và xác nhận.</p></section>
    {!loading && <section className="stat-grid pharmacist-stats"><div className="stat-card"><MaterialIcon name="group" size={20} /><div className="stat-value">{patients.length}</div><div className="stat-label">Tổng bệnh nhân</div></div><div className={`stat-card ${urgentCount ? "attention" : ""}`}><MaterialIcon name="priority_high" size={20} /><div className="stat-value">{urgentCount}</div><div className="stat-label">Cần xử lý gấp</div></div></section>}
    {loading && <div className="loading-row"><span className="spinner" /> Đang tải danh sách...</div>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {!loading && patients.length === 0 && <div className="empty-state"><MaterialIcon name="group_off" size={40} /><strong>Chưa có bệnh nhân</strong><span>Chưa có hồ sơ nào được phân công cho bạn.</span></div>}
    <section className="patient-list">{patients.map((p) => <article key={p.id} className={`patient-card patient-card--large ${p.co_canh_bao_nang_chua_xu_ly ? "patient-card--urgent" : ""}`}><div className="patient-card__info"><span className="avatar avatar--large">{getInitials(p.ho_ten)}</span><div><h2>{p.ho_ten}</h2><p>{p.co_canh_bao_nang_chua_xu_ly ? "Có cảnh báo nghiêm trọng cần xử lý" : "Hồ sơ đang ổn định"}</p></div></div><div className="patient-card__footer">{p.co_canh_bao_nang_chua_xu_ly ? <span className="badge badge-urgent"><MaterialIcon name="warning" size={14} /> Cần xử lý gấp</span> : <span className="badge badge-ok"><MaterialIcon name="check_circle" size={14} /> Ổn định</span>}<button className="secondary" onClick={() => router.push(`/review?patientId=${p.id}`)}>Xem hồ sơ <MaterialIcon name="arrow_forward" size={18} /></button></div></article>)}</section>
  </main>;
}
