"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, listPatientChecks, type InteractionCheckSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";

export default function HistoryPage() {
  const router = useRouter();
  const session = getSession();
  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    listPatientChecks(session.userId, session.accessToken).then(setChecks).catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được lịch sử kiểm tra"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!session) return null;
  return <main className="history-page">
    <section className="page-intro"><p className="eyebrow">THEO DÕI AN TOÀN</p><h1>Lịch sử kiểm tra</h1><p>Xem lại các lần kiểm tra tương tác thuốc trước đây của bạn.</p></section>
    {error && <p className="error-text" role="alert">{error}</p>}
    {checks.length === 0 && !error && <div className="empty-state"><MaterialIcon name="history" size={40} /><strong>Chưa có lịch sử kiểm tra</strong><span>Các lần kiểm tra tương tác sẽ xuất hiện ở đây.</span></div>}
    <div className="history-grid">{checks.map((check) => <button className="history-tile" key={check.id} onClick={() => router.push(`/check-result?checkId=${check.id}`)}><div className="history-tile__top"><span>{new Date(check.thoi_gian_kiem_tra).toLocaleString("vi-VN")}</span><b className={check.trang_thai_xac_nhan === "da_xac_nhan" ? "history-status history-status--confirmed" : "history-status history-status--pending"}><MaterialIcon name={check.trang_thai_xac_nhan === "da_xac_nhan" ? "check_circle" : "schedule"} size={14} />{check.trang_thai_xac_nhan === "da_xac_nhan" ? "Đã xác nhận" : "Chưa xác nhận"}</b></div><strong>Thuốc đã kiểm tra</strong><div className="history-tile__chips"><span><MaterialIcon name="medication" size={15} />Kết quả tương tác</span></div><div className="history-tile__bottom"><span>{check.co_canh_bao_nang ? "Có cảnh báo cần chú ý" : "Chưa phát hiện cảnh báo nghiêm trọng"}</span><MaterialIcon name="chevron_right" size={20} /></div></button>)}</div>
  </main>;
}
