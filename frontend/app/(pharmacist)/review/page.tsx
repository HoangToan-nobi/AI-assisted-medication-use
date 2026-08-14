"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Disclaimer from "@/components/Disclaimer";
import MaterialIcon from "@/components/MaterialIcon";
import InteractionGraphExplorer from "@/components/graph/InteractionGraphExplorer";
import {
  ApiError,
  getInteractionCheckDetail,
  getPatientProfile,
  listPharmacistRequests,
  submitPharmacistReview,
  type AgentCheckResult,
  type PatientProfileInfo,
  type ReviewRequestSummary,
} from "@/lib/api";
import { getSession } from "@/lib/auth";
import { productNamesFromExplanations } from "@/lib/interactionGraph";
import type { Prescription } from "@/lib/prescription";

function ReviewContent() {
  const router = useRouter();
  const checkId = useSearchParams().get("checkId");
  const session = getSession();
  const [reviewRequest, setReviewRequest] = useState<ReviewRequestSummary | null>(null);
  const [profile, setProfile] = useState<PatientProfileInfo | null>(null);
  const [detail, setDetail] = useState<AgentCheckResult | null>(null);
  const [ghiChu, setGhiChu] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!session || !checkId) return;

    setLoading(true);
    listPharmacistRequests(session.accessToken).then(requests => {
      const req = requests.find(r => r.check_id === checkId);
      if (req) {
        setReviewRequest(req);
        // Chỉ đọc hồ sơ cá nhân (chung, không snapshot) khi bệnh nhân CHỌN gửi kèm -
        // nếu không, dùng đúng thông tin tự nhập lúc gửi yêu cầu (xem req bên dưới).
        if (req.gui_kem_ho_so) {
          getPatientProfile(req.patient_id, session.accessToken).then(setProfile).catch(err => console.error(err));
        }
      }
    }).catch(err => console.error(err));

    getInteractionCheckDetail(checkId, session.accessToken)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được chi tiết lần kiểm tra"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkId]);

  // Dược sĩ xem lại cùng đúng graph phân cấp như bệnh nhân/tab tra cứu - dựng 1
  // "đơn thuốc" tổng hợp từ danh sách thuốc xuất hiện trong các cặp giải thích
  // (không có thông tin đơn thuốc gốc để tách theo đơn).
  const prescriptions: Prescription[] = useMemo(() => {
    if (!detail?.explanations) return [];
    const names = productNamesFromExplanations(detail.explanations);
    return [{ id: "review-check", label: "Thuốc đã kiểm tra", drugs: names.map((name) => ({ name, known: true })) }];
  }, [detail]);

  // Chỉ hiện ĐÚNG danh sách thuốc của LẦN TRA CỨU NÀY (từ detail.explanations),
  // không phải "đơn thuốc của tôi" chung của bệnh nhân.
  const productNames = prescriptions[0]?.drugs.map((d) => d.name) ?? [];
  const isConfirmed = reviewRequest?.trang_thai_xac_nhan === "da_xac_nhan";

  async function handleConfirm() {
    if (!session || !checkId) return;
    setSubmitting(true); setError(null);
    try {
      await submitPharmacistReview(checkId, ghiChu, session.accessToken);
      setSubmitted(true);
      router.replace("/pharmacist-dashboard");
    } catch (err) { setError(err instanceof ApiError ? err.message : "Không xác nhận được"); }
    finally { setSubmitting(false); }
  }

  if (!session) return null;
  if (!checkId) {
    return (
      <main>
        <div className="empty-state">
          <MaterialIcon name="search" size={40} />
          <strong>Không tìm thấy yêu cầu</strong>
          <span>Vui lòng chọn yêu cầu xét duyệt từ bảng điều khiển.</span>
          <button onClick={() => router.push("/pharmacist-dashboard")}>Về trang chủ</button>
        </div>
      </main>
    );
  }

  return (
    <main>
      <div className="page-header page-header--in-content">
        <button className="page-header__back" onClick={() => router.push("/pharmacist-dashboard")} aria-label="Quay lại">
          <MaterialIcon name="arrow_back" size={22} />
        </button>
        <div>
          <p className="eyebrow">XEM XÉT CHUYÊN MÔN</p>
          <h1 className="page-header__title">{reviewRequest ? `Hồ sơ: ${reviewRequest.patient_name}` : "Chi tiết cảnh báo"}</h1>
        </div>
      </div>

      {loading && <div className="loading-row"><span className="spinner" /> Đang tải...</div>}
      {error && <p className="error-text" role="alert">{error}</p>}

      <div className="review-layout">
        <div className="review-layout__main">
          {!loading && (
        <section className="panel profile-medications">
          <div className="dashboard-section__header"><h2>Thông tin người được kiểm tra</h2></div>
          {reviewRequest?.gui_kem_ho_so ? (
            (profile?.ngay_sinh || profile?.benh_nen_ghi_chu) ? (
              <div className="field" style={{ marginBottom: 16 }}>
                {profile?.ngay_sinh && <p><strong>Ngày sinh:</strong> {profile.ngay_sinh}</p>}
                {profile?.benh_nen_ghi_chu && <p><strong>Bệnh nền / ghi chú:</strong> {profile.benh_nen_ghi_chu}</p>}
              </div>
            ) : (
              <p className="empty-state__hint">Bệnh nhân chưa cập nhật thông tin cá nhân.</p>
            )
          ) : reviewRequest?.ten_nguoi_duoc_kiem_tra ? (
            <div className="field" style={{ marginBottom: 16 }}>
              <p><strong>Người được kiểm tra:</strong> {reviewRequest.ten_nguoi_duoc_kiem_tra}</p>
              {reviewRequest.ngay_sinh_nhap_tay && <p><strong>Ngày sinh:</strong> {reviewRequest.ngay_sinh_nhap_tay}</p>}
              {reviewRequest.ghi_chu_nhap_tay && <p><strong>Ghi chú:</strong> {reviewRequest.ghi_chu_nhap_tay}</p>}
            </div>
          ) : (
            <p className="empty-state__hint">Người bệnh không gửi kèm thông tin cá nhân.</p>
          )}

          <h3 style={{ marginBottom: 8 }}>Thuốc trong lần tra cứu này</h3>
          {productNames.length === 0 && <p className="empty-state__hint">Không có thuốc nào.</p>}
          {productNames.map((name) => (
            <article className="profile-medication" key={name}>
              <span className="profile-medication__icon"><MaterialIcon name="medication" size={22} /></span>
              <div><strong>{name}</strong></div>
            </article>
          ))}
        </section>
      )}


      {detail && prescriptions.length > 0 && (
        <InteractionGraphExplorer
          result={{
            explanations: detail.explanations ?? [],
            has_severe: detail.has_severe ?? false,
            has_unclassified: detail.has_unclassified ?? false,
            product_explanations: detail.product_explanations ?? [],
            prescription_explanations: detail.prescription_explanations ?? [],
          }}
          prescriptions={prescriptions}
          audience="pharmacist"
        />
      )}
          <Disclaimer />
        </div>

        <div className="review-layout__sidebar">
          {checkId && isConfirmed ? (
            <section className="review-form panel" style={{ margin: 0 }}>
              <div className="section__header">
                <h2 className="section__title"><MaterialIcon name="check_circle" size={20} /> Đã xem xét</h2>
              </div>
              <p className="eyebrow" style={{ marginBottom: 10 }}>NHẬN XÉT ĐÃ LƯU</p>
              <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{reviewRequest.ghi_chu || "Dược sĩ chưa để lại ghi chú."}</p>
              {reviewRequest.thoi_gian_xac_nhan && (
                <p className="empty-state__hint" style={{ marginTop: 14 }}>
                  Xác nhận lúc {new Date(reviewRequest.thoi_gian_xac_nhan).toLocaleString("vi-VN")}
                </p>
              )}
              <button className="secondary" style={{ marginTop: 18 }} onClick={() => router.push("/pharmacist-dashboard")}>
                <MaterialIcon name="arrow_back" size={18} /> Về trang chủ
              </button>
            </section>
          ) : checkId && (
            <section className="review-form panel" style={{ margin: 0 }}>
              <div className="section__header"><h2 className="section__title"><MaterialIcon name="edit_note" size={20} /> Ghi nhận xét chuyên môn</h2></div>
              <div className="field">
                <label htmlFor="ghi_chu">Ghi chú của dược sĩ</label>
                <textarea id="ghi_chu" rows={4} value={ghiChu} onChange={(e) => setGhiChu(e.target.value)} placeholder="Ví dụ: Đã tư vấn bệnh nhân, trao đổi với bác sĩ điều trị..." />
              </div>
              <button className="btn-block" onClick={handleConfirm} disabled={submitting}>
                {submitting ? <><span className="spinner spinner--sm" /> Đang lưu...</> : <><MaterialIcon name="check_circle" size={20} /> Xác nhận đã xem xét</>}
              </button>
              {submitted && <p className="success-text"><MaterialIcon name="check_circle" size={18} /> Đã xác nhận thành công</p>}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

export default function PharmacistReviewPage() {
  return (
    <Suspense fallback={<main><div className="loading-row"><span className="spinner" /> Đang tải...</div></main>}>
      <ReviewContent />
    </Suspense>
  );
}
