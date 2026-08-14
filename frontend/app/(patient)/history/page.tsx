"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MaterialIcon from "@/components/MaterialIcon";
import { ApiError, listPatientChecks, deletePatientCheck, deleteAllPatientChecks, type InteractionCheckSummary } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { formatVietnameseDateTime } from "@/lib/datetime";

type StatusFilter = "all" | "da_xac_nhan" | "cho_xac_nhan" | "chua_xac_nhan";

const STATUS_LABEL: Record<Exclude<StatusFilter, "all">, string> = {
  da_xac_nhan: "Đã xác nhận",
  cho_xac_nhan: "Chờ xác nhận",
  chua_xac_nhan: "Không gửi",
};

const STATUS_ICON: Record<Exclude<StatusFilter, "all">, string> = {
  da_xac_nhan: "check_circle",
  cho_xac_nhan: "schedule",
  chua_xac_nhan: "remove_circle_outline",
};

export default function HistoryPage() {
  const router = useRouter();
  const session = getSession();
  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");

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

  // Sắp mới -> cũ (backend đã sort sẵn, sort lại phía client cho chắc), rồi lọc
  // theo nhãn trạng thái xác nhận đang chọn.
  const visibleChecks = useMemo(() => {
    const sorted = [...checks].sort(
      (a, b) => new Date(b.thoi_gian_kiem_tra).getTime() - new Date(a.thoi_gian_kiem_tra).getTime()
    );
    return filter === "all" ? sorted : sorted.filter((c) => c.trang_thai_xac_nhan === filter);
  }, [checks, filter]);

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

      {checks.length > 0 && (
        <div className="profile-tabs" role="tablist" aria-label="Lọc theo trạng thái xác nhận">
          <button type="button" role="tab" aria-selected={filter === "all"} className={`profile-tabs__item ${filter === "all" ? "profile-tabs__item--active" : ""}`} onClick={() => setFilter("all")}>Tất cả</button>
          {(Object.keys(STATUS_LABEL) as Exclude<StatusFilter, "all">[]).map((key) => (
            <button key={key} type="button" role="tab" aria-selected={filter === key} className={`profile-tabs__item ${filter === key ? "profile-tabs__item--active" : ""}`} onClick={() => setFilter(key)}>
              {STATUS_LABEL[key]}
            </button>
          ))}
        </div>
      )}

      {checks.length === 0 && !error && (
        <div className="empty-state">
          <MaterialIcon name="history" size={40} />
          <strong>Chưa có lịch sử kiểm tra</strong>
          <span>Các lần kiểm tra tương tác sẽ xuất hiện ở đây.</span>
        </div>
      )}
      {checks.length > 0 && visibleChecks.length === 0 && (
        <div className="empty-state">
          <MaterialIcon name="filter_list_off" size={40} />
          <strong>Không có lịch sử phù hợp bộ lọc</strong>
          <span>Thử chọn nhãn khác hoặc chọn "Tất cả".</span>
        </div>
      )}
      <div className="history-grid">
        {visibleChecks.map((check) => {
          const status = (check.trang_thai_xac_nhan as Exclude<StatusFilter, "all">) in STATUS_LABEL
            ? (check.trang_thai_xac_nhan as Exclude<StatusFilter, "all">)
            : "chua_xac_nhan";
          return (
          <div
            className="history-tile"
            key={check.id}
            onClick={() => router.push(`/check-result?checkId=${check.id}`)}
            style={{ cursor: "pointer", position: "relative" }}
          >
            <div className="history-tile__top">
              <span>{formatVietnameseDateTime(check.thoi_gian_kiem_tra)}</span>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <b className={`history-status history-status--${status === "da_xac_nhan" ? "confirmed" : status === "cho_xac_nhan" ? "pending" : "not-sent"}`}>
                  <MaterialIcon name={STATUS_ICON[status]} size={14} />
                  {STATUS_LABEL[status]}
                </b>
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
          );
        })}
      </div>
    </main>
  );
}
