"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, listPatientChecks, deletePatientCheck, deleteAllPatientChecks, type InteractionCheckSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { formatVietnameseDateTime } from "@/lib/datetime";

export default function HistoryPage() {
  const router = useRouter();
  const session = getSession();
  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchChecks = () => {
    if (!session) return;
    listPatientChecks(session.userId, session.accessToken)
      .then(setChecks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được lịch sử kiểm tra"));
  };

  useEffect(() => {
    fetchChecks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDeleteAll = async () => {
    if (!session) return;
    if (!confirm("Bạn có chắc chắn muốn xóa tất cả lịch sử tra cứu?")) return;
    try {
      await deleteAllPatientChecks(session.userId, session.accessToken);
      fetchChecks();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Lỗi khi xóa tất cả lịch sử");
    }
  };

  const handleDeleteCheck = async (e: React.MouseEvent, checkId: string) => {
    e.stopPropagation();
    if (!session) return;
    if (!confirm("Bạn có chắc chắn muốn xóa lịch sử này?")) return;
    try {
      await deletePatientCheck(session.userId, checkId, session.accessToken);
      fetchChecks();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Lỗi khi xóa lịch sử");
    }
  };

  if (!session) return null;
  return (
    <main className="history-page">
      <section className="page-intro" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <p className="eyebrow">THEO DÕI AN TOÀN</p>
          <h1>Lịch sử kiểm tra</h1>
          <p>Xem lại các lần kiểm tra tương tác thuốc trước đây của bạn.</p>
        </div>
        {checks.length > 0 && (
          <button className="btn-severe" onClick={handleDeleteAll} style={{ padding: "8px 16px", borderRadius: "8px" }}>
            <MaterialIcon name="delete" size={18} /> Xóa tất cả
          </button>
        )}
      </section>
      {error && <p className="error-text" role="alert">{error}</p>}
      {checks.length === 0 && !error && (
        <div className="empty-state">
          <MaterialIcon name="history" size={40} />
          <strong>Chưa có lịch sử kiểm tra</strong>
          <span>Các lần kiểm tra tương tác sẽ xuất hiện ở đây.</span>
        </div>
      )}
      <div className="history-grid">
        {checks.map((check) => (
          <div 
            className="history-tile" 
            key={check.id} 
            onClick={() => router.push(`/check-result?checkId=${check.id}`)}
            style={{ cursor: "pointer", position: "relative" }}
          >
            <div className="history-tile__top">
              <span>{formatVietnameseDateTime(check.thoi_gian_kiem_tra)}</span>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                {check.co_canh_bao_nang && (
                  <b className={check.trang_thai_xac_nhan === "da_xac_nhan" ? "history-status history-status--confirmed" : "history-status history-status--pending"}>
                    <MaterialIcon name={check.trang_thai_xac_nhan === "da_xac_nhan" ? "check_circle" : "schedule"} size={14} />
                    {check.trang_thai_xac_nhan === "da_xac_nhan" ? "Đã xác nhận" : "Chưa xác nhận"}
                  </b>
                )}
                <button
                  onClick={(e) => handleDeleteCheck(e, check.id)}
                  style={{ background: "none", border: "none", color: "var(--danger)", cursor: "pointer", display: "flex" }}
                  title="Xóa"
                >
                  <MaterialIcon name="delete" size={20} />
                </button>
              </div>
            </div>
            <strong>Thuốc đã kiểm tra</strong>
            <div className="history-tile__chips">
              <span><MaterialIcon name="medication" size={15} />Kết quả tương tác</span>
            </div>
            <div className="history-tile__bottom">
              <span>{check.co_canh_bao_nang ? "Có cảnh báo cần chú ý" : "Chưa phát hiện cảnh báo nghiêm trọng"}</span>
              <MaterialIcon name="chevron_right" size={20} />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
