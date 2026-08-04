"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AlertCard from "@/components/AlertCard";
import Disclaimer from "@/components/Disclaimer";
import {
  ApiError,
  getInteractionCheckDetail,
  listPatientChecksForPharmacist,
  submitPharmacistReview,
  type AgentCheckResult,
  type InteractionCheckSummary,
} from "@/lib/api";
import { getSession } from "@/lib/auth";

function ReviewContent() {
  const searchParams = useSearchParams();
  const patientId = searchParams.get("patientId");
  const session = getSession();

  const [checks, setChecks] = useState<InteractionCheckSummary[]>([]);
  const [selectedCheckId, setSelectedCheckId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentCheckResult | null>(null);
  const [ghiChu, setGhiChu] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!session || !patientId) return;
    listPatientChecksForPharmacist(patientId, session.accessToken)
      .then((list) => {
        setChecks(list);
        if (list.length > 0) setSelectedCheckId(list[0].id);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được danh sách lần kiểm tra")
      )
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  useEffect(() => {
    if (!session || !selectedCheckId) return;
    setSubmitted(false);
    setGhiChu("");
    getInteractionCheckDetail(selectedCheckId, session.accessToken)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Không tải được chi tiết")
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCheckId]);

  async function handleConfirm() {
    if (!session || !selectedCheckId) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitPharmacistReview(selectedCheckId, ghiChu, session.accessToken);
      setSubmitted(true);
      setChecks((prev) =>
        prev.map((c) =>
          c.id === selectedCheckId ? { ...c, trang_thai_xac_nhan: "da_xac_nhan" } : c
        )
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không xác nhận được");
    } finally {
      setSubmitting(false);
    }
  }

  if (!session) return null;
  if (!patientId) {
    return (
      <main>
        <p>Thiếu thông tin bệnh nhân — vui lòng chọn từ danh sách bệnh nhân phụ trách.</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Xem xét cảnh báo</h1>

      {loading && (
        <div className="loading-row">
          <span className="spinner" aria-hidden="true" />
          Đang tải...
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
      {!loading && checks.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            📭
          </span>
          Bệnh nhân này chưa có lần kiểm tra nào.
        </div>
      )}

      {checks.length > 1 && (
        <div className="field">
          <label htmlFor="check_select">Lần kiểm tra</label>
          <select
            id="check_select"
            value={selectedCheckId ?? ""}
            onChange={(e) => setSelectedCheckId(e.target.value)}
          >
            {checks.map((c) => (
              <option key={c.id} value={c.id}>
                {new Date(c.thoi_gian_kiem_tra).toLocaleString("vi-VN")}
                {c.co_canh_bao_nang ? " — Nghiêm trọng" : ""}
                {c.trang_thai_xac_nhan === "da_xac_nhan" ? " (đã xác nhận)" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {detail?.explanations?.map((e, idx) => (
        <AlertCard
          key={idx}
          thuocA={e.thuoc_a}
          thuocB={e.thuoc_b}
          severity={e.muc_do}
          description={e.giai_thich}
          source={e.nguon_trich_dan}
          management={e.xu_tri}
        />
      ))}

      <Disclaimer />

      {selectedCheckId && (
        <div className="panel">
          <div className="field">
            <label htmlFor="ghi_chu">Ghi chú của dược sĩ</label>
            <textarea
              id="ghi_chu"
              rows={4}
              value={ghiChu}
              onChange={(e) => setGhiChu(e.target.value)}
              placeholder="VD: đã tư vấn bệnh nhân trao đổi với bác sĩ điều trị..."
            />
          </div>

          <button onClick={handleConfirm} disabled={submitting}>
            {submitting && <span className="spinner" aria-hidden="true" />}
            {submitting ? "Đang lưu..." : "✓ Xác nhận đã xem xét"}
          </button>

          {submitted && <span className="badge badge-success" style={{ marginLeft: 12 }}>Đã xác nhận thành công</span>}
        </div>
      )}
    </main>
  );
}

export default function PharmacistReviewPage() {
  return (
    <Suspense
      fallback={
        <main>
          <p>Đang tải...</p>
        </main>
      }
    >
      <ReviewContent />
    </Suspense>
  );
}
